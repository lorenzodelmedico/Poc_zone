"""Confluence REST : même contrat content/storage que le collecteur existant."""
import json
import os
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import parse_qs, unquote, urlsplit
from xml.etree import ElementTree

from dotenv import dotenv_values
import requests

from .settings import ROOT, KitError, checked_url
from .workspace import WorkflowError


class PageText(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.parts, self.headings, self.heading = [], [], None
        self.hidden = 0
        self.feed(content)
        self.close()
        self.text = "".join(self.parts)

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if self.hidden:
            return
        if re.fullmatch(r"h[1-6]", tag):
            self.parts.append("\n")
            self.heading = {"level": int(tag[1]), "start": len("".join(self.parts)), "title": ""}
        elif tag in {"p", "div", "li", "tr", "br", "pre"}:
            self.parts.append("\n")
        elif tag in {"td", "th"}:
            self.parts.append("\t")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
            return
        if self.hidden:
            return
        if re.fullmatch(r"h[1-6]", tag) and self.heading is not None:
            self.parts.append("\n")
            self.heading["body"] = len("".join(self.parts))
            self.headings.append(self.heading)
            self.heading = None
        elif tag in {"p", "div", "li", "tr", "pre"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)
            if self.heading is not None:
                self.heading["title"] += data

    def unknown_decl(self, data):
        if data.startswith("CDATA["):
            self.handle_data(data[6:])


def checked_content(content):
    if not isinstance(content, str) or not content.strip():
        raise WorkflowError("Contenu XHTML Confluence non vide requis.")
    if "<!DOCTYPE" in content.upper() or "<!ENTITY" in content.upper():
        raise WorkflowError("Déclaration XML non autorisée dans le contenu.")
    try:
        ElementTree.fromstring('<root xmlns:ac="http://atlassian.com/content" '
                               'xmlns:ri="http://atlassian.com/resource/identifier">' + content + '</root>')
    except ElementTree.ParseError:
        raise WorkflowError("XHTML Confluence invalide ; échapper notamment les & et < du texte/code.") from None
    return content


class Confluence:
    def __init__(self, env_file=None):
        self.env_file = Path(env_file or ROOT / ".env").expanduser().resolve()
        self.env = {
            name: value.strip()
            for values in (dotenv_values(self.env_file, interpolate=False, encoding="utf-8-sig"), os.environ)
            for name, value in values.items()
            if isinstance(value, str) and value.strip()
        }
        self.token = (self.env.get("CONFLUENCE_TOKEN") or "").strip()
        if not self.token:
            raise WorkflowError("CONFLUENCE_TOKEN requis.")
        base = self.env.get("CONFLUENCE_BASE_URL", "")
        try:
            self.base = checked_url(base, "CONFLUENCE_BASE_URL").rstrip("/")
        except (KitError, ValueError, TypeError):
            raise WorkflowError("CONFLUENCE_BASE_URL invalide.") from None
        self.origin = urlsplit(self.base)
        ca = self.env.get("CA_BUNDLE", "")
        if ca:
            path = Path(ca).expanduser()
            path = path if path.is_absolute() else self.env_file.parent / path
            if not path.is_file():
                raise WorkflowError("CA_BUNDLE ne désigne pas un fichier CA.")
            self.verify = str(path.resolve())
        else:
            self.verify = True

    def urls(self, name):
        try:
            items = json.loads(self.env.get(name) or "[]")
        except (ValueError, TypeError):
            raise WorkflowError(f"{name} : tableau JSON d’URL attendu.") from None
        if not isinstance(items, list) or any(not isinstance(x, str) or not x.strip() for x in items):
            raise WorkflowError(f"{name} : tableau JSON d’URL attendu.")
        return list(dict.fromkeys(items))

    def call(self, method, path, **kwargs):
        try:
            with requests.Session() as session:
                # Même bearer Confluence que le collecteur photographié, pour GET/POST/PUT.
                response = session.request(method, self.base + path,
                    headers={"Accept": "application/json", "Authorization": f"Bearer {self.token}"},
                    verify=self.verify,
                    auth=lambda request: request, timeout=(10, 60), allow_redirects=False, **kwargs)
                if not 200 <= response.status_code < 300:
                    raise WorkflowError(f"Confluence : HTTP {response.status_code}.")
                value = response.json()
                if not isinstance(value, dict):
                    raise ValueError
                return value
        except (requests.RequestException, ValueError) as exc:
            raise WorkflowError("Confluence : " + type(exc).__name__ + ".") from None

    def page(self, page_id):
        if not str(page_id).isdigit():
            raise WorkflowError("Identifiant de page Confluence invalide.")
        page = self.call("GET", "/rest/api/content/" + str(page_id),
                         params={"expand": "body.storage,version,space,ancestors", "status": "current"})
        try:
            page["body"]["storage"]["value"]
            page["version"]["number"]
            page["space"]["key"]
            if page.get("type", "page") != "page":
                raise KeyError
        except (KeyError, TypeError):
            raise WorkflowError("Réponse Confluence incomplète pour une page.") from None
        return page

    def resolve(self, url):
        try:
            u = urlsplit(url)
            if (u.scheme, u.hostname, u.port) != (self.origin.scheme, self.origin.hostname, self.origin.port):
                raise ValueError
            if u.username or u.password or "\\" in url or any(c.isspace() for c in url):
                raise ValueError
            prefix = self.origin.path.rstrip("/")
            if prefix and not u.path.startswith(prefix + "/"):
                raise ValueError
            path = u.path[len(prefix):]
            ids = parse_qs(u.query).get("pageId", [])
            if not ids:
                match = re.search(r"/(?:pages|content)/(\d+)(?:/|$)", path)
                ids = [match[1]] if match else []
            if ids:
                return self.page(ids[0])
            if path.startswith("/display/"):
                space, title = path[len("/display/"):].split("/", 1)
                result = self.call("GET", "/rest/api/content", params={
                    "spaceKey": unquote(space), "title": unquote(title.replace("+", " ")),
                    "type": "page", "status": "current", "limit": 2})
                if len(result.get("results", [])) == 1:
                    return self.page(result["results"][0]["id"])
        except (ValueError, TypeError, AttributeError):
            pass
        raise WorkflowError("URL de page de l’instance configurée requise ; utiliser le lien contenant pageId si nécessaire.")

    def public(self, page):
        return {"id": str(page["id"]), "title": page["title"],
                "version": page["version"]["number"], "space": page["space"]["key"],
                "url": self.base + "/pages/viewpage.action?pageId=" + str(page["id"])}

    def read_many(self, urls=None, offset=0, limit=12000, format="text"):
        if offset < 0 or not 1 <= limit <= 30000:
            raise WorkflowError("offset >= 0 et 1 <= limit <= 30000 requis.")
        if format not in {"text", "storage"}:
            raise WorkflowError("format doit valoir text ou storage.")
        urls = self.urls("CONFLUENCE_PAGE_URLS") if urls is None else urls
        if not isinstance(urls, list) or any(not isinstance(url, str) for url in urls):
            raise WorkflowError("urls doit être une liste d’URL.")
        budget = max(1, limit // max(1, len(urls)))
        results, seen = [], set()
        for url in urls:
            try:
                page = self.resolve(url)
                if str(page["id"]) in seen:
                    continue
                seen.add(str(page["id"]))
                body = page["body"]["storage"]["value"]
                text = body if format == "storage" else PageText(body).text
                end = min(len(text), offset + budget)
                results.append({**self.public(page), "content": text[offset:end],
                                "format": format, "offset": offset, "total_chars": len(text),
                                "next_offset": end if end < len(text) else None})
            except WorkflowError as exc:
                results.append({"url": url, "error": str(exc)})
        return {"pages": results, "empty": not results}

    def guides(self):
        result, seen = [], set()
        for url in self.urls("SCHEMA_TECHNIQUE_CONFLUENCE"):
            try:
                page = self.resolve(url)
                if str(page["id"]) not in seen:
                    result.append(self.public(page))
                    seen.add(str(page["id"]))
            except WorkflowError as exc:
                result.append({"url": url, "error": str(exc)})
        return result

    def guide(self, url, section_titles=None):
        page = self.resolve(url)
        parsed = PageText(page["body"]["storage"]["value"])
        headings = [h for h in parsed.headings if h["title"].strip() != page["title"].strip()]
        if not headings:
            if (not isinstance(section_titles, list) or not section_titles
                    or any(not isinstance(t, str) or not t.strip() for t in section_titles)):
                raise WorkflowError("Lire le guide avec confluence_pages, en déduire ses rubriques fidèlement, puis choose avec section_titles.")
            return {**self.public(page), "instructions": parsed.text.strip(),
                    "sections": [{"id": str(i), "title": title.strip(), "guidance": "", "content": None}
                                 for i, title in enumerate(section_titles, 1)]}
        level = min(h["level"] for h in headings)
        if sum(h["level"] == 1 for h in headings) <= 1 and any(h["level"] == 2 for h in headings):
            level = 2
        headings = [h for h in headings if h["level"] == level]
        sections = []
        for i, h in enumerate(headings):
            end = headings[i + 1]["start"] if i + 1 < len(headings) else len(parsed.text)
            sections.append({"id": str(i + 1), "title": h["title"].strip(),
                             "guidance": parsed.text[h["body"]:end].strip(), "content": None})
        return {**self.public(page), "instructions": parsed.text[:headings[0]["start"]].strip(),
                "sections": sections}

    def write(self, draft, body):
        payload = {"type": "page", "title": draft["title"],
                   "body": {"storage": {"value": body, "representation": "storage"}}}
        if draft.get("page_id"):
            current = self.page(draft["page_id"])
            if current["version"]["number"] != draft["version"]:
                raise WorkflowError("Version distante modifiée ; relire la page et préparer une nouvelle proposition.")
            payload["version"] = {"number": draft["version"] + 1}
            return self.call("PUT", "/rest/api/content/" + draft["page_id"], json=payload)
        payload.update(space={"key": draft["space"]}, ancestors=[{"id": draft["parent_id"]}])
        return self.call("POST", "/rest/api/content", json=payload)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     return True
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     if not self.acquire():
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 self.wait_ready()
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             return True
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     self.publish("starting")
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             return False
