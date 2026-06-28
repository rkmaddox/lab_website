# Maddox Lab Website

Lab website for the Maddox Lab at the Kresge Hearing Research Institute, University of Michigan.

Built with [Jekyll](https://jekyllrb.com/) and hosted on [GitHub Pages](https://pages.github.com/).

---

## How It Works

All website content lives in simple data files inside the `_data/` folder. You edit those files to update the site — you never need to touch HTML or CSS.

When you push changes to GitHub, the site automatically rebuilds in about 30 seconds.

---

## Common Tasks

### Add a New Lab Member

1. Open `_data/people.yml`
2. Add a new entry at the bottom:

```yaml
- name: Jane Smith
  role: PhD Student
  title: "Biomedical Engineering"
  photo: jane-smith.jpg
  email: jsmith@umich.edu
  website: ""
  scholar: ""
  bio: >
    Jane studies subcortical responses to natural speech
    using the auditory brainstem response.
```

3. Upload their headshot to `assets/images/people/` (square images work best, ~400x400px)
4. Commit and push

### Move Someone to Alumni

1. Remove their entry from `_data/people.yml`
2. Add them to `_data/alumni.yml`:

```yaml
- name: Jane Smith
  role: "PhD Student (2024-2028)"
  now: "Postdoc at MIT"
```

3. Commit and push

### Update Publications (automatic)

The publications page can be auto-populated from PubMed and bioRxiv/medRxiv:

```bash
pip install -r requirements.txt   # first time only
python fetch_publications.py
```

This script:
1. Searches PubMed for all papers by "maddox rk"
2. Searches bioRxiv/medRxiv for preprints by the same author
3. Checks each preprint to see if it has been published — if so, only the
   published version is included
4. Unpublished preprints are marked with bold **Preprint.** on the website
5. Writes `_data/publications.yml`

**Your manual edits to `highlight` and `pdf` fields are preserved** when you
re-run the script. So you can mark key papers and add PDF links without
worrying about them being overwritten.

### Add a Publication (manual)

You can also edit `_data/publications.yml` by hand. Find the correct year
(or add a new year block at the top):

```yaml
- year: 2026
  papers:
    - title: "Your paper title here"
      authors: "Maddox RK, Smith J"
      journal: "Journal of Neuroscience"
      volume: "46(3), 123-135"
      doi: "https://doi.org/10.xxxx/xxxxx"
      pdf: ""
      highlight: false
      preprint: false
```

Set `highlight: true` for key papers (they get an accent border).
Set `preprint: true` for papers that should show bold "Preprint." label.

### Add a New Research Area

1. Open `_data/research.yml`
2. Add a new entry:

```yaml
- title: New Research Direction
  image: new-direction.jpg
  description: >
    Description of the new research area, its goals,
    methods, and significance.
```

3. Optionally upload an image to `assets/images/research/`
4. Commit and push

### Add or Update a Study on the Participate Page

1. Open `_data/studies.yml`
2. Add a new study or change `active: true` / `active: false`:

```yaml
- title: "Listening in Noise Study"
  description: >
    We are looking for adults with normal hearing to participate
    in a study on speech processing in noisy environments.
  eligibility: "Adults aged 18-35 with normal hearing"
  compensation: "$20/hour"
  contact: "rkmaddox@umich.edu"
  active: true
```

3. Setting `active: false` hides the study without deleting it
4. Commit and push

### Update Funding

1. Open `_data/funding.yml`
2. Add or edit entries:

```yaml
- name: "National Institutes of Health (NIDCD)"
  logo: nih-nidcd.png
  url: "https://www.nidcd.nih.gov/"
  grant: "R01 DC012345"
```

3. Upload logos to `assets/images/logos/`
4. Commit and push

---

## YAML Syntax Tips

YAML is the format used for the data files. Here are the key rules:

- **Indentation matters**: Use 2 spaces (not tabs) for each level of indentation
- **Each list item starts with `- `** (dash + space)
- **Quotes**: Put values in quotes if they contain colons, e.g., `title: "Part 1: Methods"`
- **Multi-line text**: Use `>` followed by indented lines for paragraphs:
  ```yaml
  bio: >
    This is a paragraph that can span
    multiple lines. It will be joined
    into one paragraph.
  ```
- **Empty values**: Use `""` for fields you want to leave blank
- **Comments**: Lines starting with `#` are ignored

---

## File Structure

```
_data/              ← EDIT THESE to update content
  people.yml        ← Lab members
  alumni.yml        ← Former members
  publications.yml  ← Papers by year
  research.yml      ← Research areas
  studies.yml       ← Participant studies
  funding.yml       ← Grants and sponsors
  navigation.yml    ← Nav bar links

assets/images/      ← UPLOAD IMAGES HERE
  people/           ← Headshots
  research/         ← Research area images
  logos/            ← Funder/sponsor logos

_includes/          ← Reusable HTML components (don't need to edit)
_layouts/           ← Page templates (don't need to edit)
_sass/              ← Styles (don't need to edit)
_config.yml         ← Site-wide settings
```

---

## Setting Up GitHub Pages

1. Push this repository to GitHub
2. Go to **Settings → Pages** in your GitHub repository
3. Under "Source", select **Deploy from a branch**
4. Select the **main** branch and **/ (root)** folder
5. Click **Save**
6. Your site will be live at `https://yourusername.github.io/repo-name/` in a few minutes

### Using a Custom Domain (Optional)

1. In **Settings → Pages**, enter your custom domain (e.g., `maddoxlab.org`)
2. Add a `CNAME` file to the repository root containing just the domain name
3. Configure DNS with your domain registrar (GitHub's docs explain this)

---

## Local Preview (Optional)

You do **not** need to preview locally — you can just push to GitHub and check the live site. But if you want to:

1. Install Ruby and Jekyll: https://jekyllrb.com/docs/installation/
2. Run `bundle install` (first time only)
3. Run `bundle exec jekyll serve`
4. Open `http://localhost:4000` in your browser
