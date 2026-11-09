# Dépendance ECharts

Le fichier `echarts.min.js` est une dépendance tierce à installer localement.
Aucun CDN n'est utilisé par l'application et aucun script n'est téléchargé au démarrage.

Installation depuis une archive npm approuvée, ou téléchargement explicite :

```bash
python scripts/install_echarts.py --archive /chemin/echarts-5.6.0.tgz
python scripts/install_echarts.py --download
```

Une seule de ces commandes suffit. L'installateur copie aussi LICENSE et NOTICE.
Le fichier JavaScript obtenu est servi depuis `/static/vendor/echarts.min.js`.
