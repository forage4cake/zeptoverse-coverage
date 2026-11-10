# Zeptoverse automatic coverage page

This package contains:
- `index.html`: responsive three-column coverage page.
- `scripts/collect.py`: scheduled collector. It searches GDELT and Reddit RSS, opens candidate pages, and only adds a result if the exact word “zeptoverse” is present in the readable page text.
- `data/mentions.json`: the live data feed used by the HTML.
- `.github/workflows/update.yml`: weekly Tuesday 11:10 UTC scan and GitHub Pages deployment.

## Publish it with GitHub Pages (recommended)

1. Create a GitHub repository (for example `zeptoverse-coverage`) and upload the contents of this folder to its `main` branch.
2. In the repository, open **Settings → Pages** and set **Build and deployment → Source** to **GitHub Actions**.
3. Open **Actions** and run **Update Zeptoverse coverage** once manually. The workflow will collect, verify and publish the page.
4. Your site will be available at `https://YOUR-USERNAME.github.io/REPOSITORY/` after the first successful deployment.
5. In Weebly, add an **Embed Code** element and use the iframe snippet below, replacing the URL with your GitHub Pages address:

```html
<iframe src="https://YOUR-USERNAME.github.io/REPOSITORY/"
        title="Zeptoverse coverage"
        style="width:100%;height:1500px;border:0"
        loading="lazy"></iframe>
```

The GitHub Actions workflow runs every Tuesday at 11:10 UTC. You can also trigger it manually from the Actions tab.

## Important limitations

- This is an automated discovery and verification feed, not a guarantee of complete internet coverage. GDELT and Reddit RSS do not index every page or platform.
- A candidate is only published after the collector can open the page and confirm the exact term in its readable page text. Paywalled, blocked or inaccessible pages may be missed.
- The collector does not treat general coverage of related particle physics as an exact mention.
- Images are only displayed if the source page declares a Creative Commons or public-domain licence link and exposes an Open Graph image. Otherwise the card uses an original CSS graphic. Review licence terms before reusing images.
- Reddit may rate-limit RSS requests. If it does, Reddit results may be delayed or absent from a run.
- The workflow stores prior verified results in `data/mentions.json` and deduplicates by canonical URL.

## Local preview

Open `index.html` through a local web server (not by double-clicking) so the browser can fetch `data/mentions.json`. For example, run `python -m http.server` from this folder and visit `http://localhost:8000`.
