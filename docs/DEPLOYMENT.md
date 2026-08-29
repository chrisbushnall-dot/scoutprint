# Deployment

The public dashboard is deployed from this repository by Vercel.

- Production branch: `main`
- Production URL: `https://scoutprint.vercel.app`
- Build output: `web/`
- Configuration: `vercel.json`
- Pull requests: Vercel preview deployments
- Pushes to `main`: Vercel production deployments

The Vercel build is a static, browser-native scouting dashboard backed by the precomputed profile chunks in `web/data/`. The VPS Streamlit/DuckDB service remains the exact shortlisted Sinkhorn research backend and is not exposed by Vercel.

To reproduce a deployment locally:

```bash
python -m scripts.export_web_data
vercel build
vercel deploy --prod
```
