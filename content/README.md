# Source content

The material Bay Sahne supplied, exactly as received. `python -m app.cli import-content` reads it once to
fill a new database (see [docs/CONTENT_IMPORT_REPORT.md](../docs/CONTENT_IMPORT_REPORT.md)); after that,
content is managed in the admin panel and these files are not read by the running system.

```
content/
├── BAY SAHNE BİLGİLER.docx        texts: productions, About, contact details, legal drafts
└── media/
    ├── logo/                      organisation logo (baysahnelogo1 is the one in use)
    └── <production>/              poster (…baysahne) and photographs (…pic1, …pic2, …) of one production
```

Rules the importer relies on:

- The document must sit directly in `content/` under its current name.
- The document refers to images by **file name**, so do not rename image files. Folders are only for order:
  images may be moved between them, and new folders may be added, without touching any code.
- A file name must be unique across all folders; the importer stops with a clear message if it is not.
- Most files are named `.svg` but are really JPEG, PNG or WebP. The importer detects the real format; a file
  renamed to its real extension (as `bygrbaysahne.jpeg` was) is still found.
