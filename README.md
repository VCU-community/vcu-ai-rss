# VCU News AI RSS feed

This repository converts the three newest stories on the [VCU News artificial intelligence topic page](https://news.vcu.edu/topics/artificialintelligence) into a standards-compliant RSS 2.0 feed. GitHub Actions refreshes and publishes the feed every six hours through GitHub Pages.

The generator uses only Python's standard library. It collects the three newest stories, creates stable item identifiers from the original article URLs, validates the generated XML, and stops with an error if the VCU page no longer yields stories.

## Set it up

1. Create a new **public** GitHub repository. A suggested name is `vcu-ai-rss`.
2. Upload all files from this project, including the `.github` folder, to the repository's `main` branch.
3. In the repository, open **Settings → Pages**.
4. Under **Build and deployment**, set **Source** to **GitHub Actions**.
5. Open **Actions → Generate and publish RSS → Run workflow**.
6. When the workflow succeeds, open the deployment URL shown in the workflow summary.

For a repository owned by your personal account, your Beekeeper feed URL will normally be:

```text
https://YOUR-GITHUB-USERNAME.github.io/vcu-ai-rss/rss.xml
```

Replace `YOUR-GITHUB-USERNAME` with your GitHub username. If you choose a different repository name, use that name in the URL.

For an organization-owned repository, use the organization name instead:

```text
https://YOUR-ORGANIZATION.github.io/vcu-ai-rss/rss.xml
```

## Test before connecting Beekeeper

Open the `rss.xml` URL in a browser. Then submit that same URL to the [W3C Feed Validation Service](https://validator.w3.org/feed/). After it passes, add it to Beekeeper.

Beekeeper may initially import several older stories. Check its RSS integration settings before enabling automatic posting if you do not want a backlog.

## Run it locally

```bash
python -m unittest -v
python generate_feed.py \
  --feed-url "https://YOUR-GITHUB-USERNAME.github.io/vcu-ai-rss/rss.xml"
```

The generated files appear in `public/`. They are intentionally not committed because GitHub Pages receives them directly from the workflow.

## Maintenance

- The workflow checks for updates every six hours. GitHub schedules can run later than their nominal time.
- A failed extraction does not replace the currently published feed; the last successful version remains available.
- If VCU News changes its page markup, the workflow will fail visibly instead of publishing an empty feed.
- To receive failure notices, enable GitHub Actions notifications for the repository.

This project republishes only story titles, dates, and links. It does not copy article text or images.
