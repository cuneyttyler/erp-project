# Homepage screenshots

These are screenshots of the real application with sample data, one set per
language (`-en`, `-tr`). They're generated, not hand-made:

```sh
npm install --no-save puppeteer-core
LANDING_USER=<local user> LANDING_PASSWORD=<password> node scripts/landing-screenshots.cjs
```

The script signs in to the locally running app and replaces the API's answers
*in the browser* with a sample company ("Demir Yapı Market A.Ş."), so nothing is
written to any database. Regenerate them when the screens they show change.
