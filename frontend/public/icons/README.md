# CloudPilot icons

Every icon is an SVG. Stroke and glyph icons use `currentColor`, so they take the text color of the element they sit in.

| Folder | Count | What it is |
|---|---|---|
| `ui/` | 90 | Buttons, menus, forms, toolbars (24x24, 1.75 stroke) |
| `cloud/` | 20 | Generic resource nodes for the diagram editor |
| `aws/` | 36 | Generic icons named after AWS services (ec2, s3, rds, lambda, eks, iam, ...) |
| `kubernetes/` | 16 | Concepts: pod, deployment, service, ingress, configmap, secret, namespace, node, ... |
| `docker/` | 7 | Concepts: image, container, dockerfile, compose, volume, network, registry |
| `github/octicons/` | 721 | All GitHub Octicons, 16px and 24px (`name-16.svg`, `name-24.svg`) |
| `brands/` | 66 | Technology logos: React, Python, PostgreSQL, Pydantic, FastAPI, Docker, Kubernetes, GitHub, GitHub Actions, Terraform, AWS, and more |
| `agents/` | 8 | Gradient agent avatars (64x64) |
| `status/` | 6 | Filled status icons with fixed colors |

`index.json` lists every name. `sprite.svg` bundles `ui`, `cloud`, `aws`, `k8s`, and `docker` as symbols. Open `frontend/design/icons/preview.html` to browse and search everything (kept out of `public/` so it is not served).

Served as files in this folder: `agents/`, `status/`, `brands/`, `aws/`, `cloud/` (recovered unmodified from the preview, where they were inlined). `ui/`, `kubernetes/`, `docker/` and `github/` are used through the sprite or not yet needed.

## Usage

Sprite (inherits color and size):

```html
<svg width="20" height="20" aria-hidden="true"><use href="/icons/sprite.svg#aws-ec2"/></svg>
```

Prefixes: `ui-`, `cloud-`, `aws-`, `k8s-`, `docker-`.

Brand logos with their official color:

```html
<link rel="stylesheet" href="/icons/brands/brand-colors.css">
<span class="brand-react"><!-- inline /icons/brands/react.svg --></span>
```

`brands.json` holds the hex colors. Black logos (GitHub, Vercel, JSON) have no color: leave them on `currentColor` so they work in dark mode.

Inline the SVG or use the sprite when you need `currentColor`. An `<img src>` renders it black.

## Licenses

See `NOTICE.md`. The license texts it names (`octicons-MIT.txt`, `simple-icons-CC0.md`, `material-design-icons.txt`) are not in the repository yet; the owner must add them. Octicons are MIT, Simple Icons are CC0, the AWS mark is from Material Design Icons (Apache 2.0). Brand logos remain trademarks of their owners. Icons in `aws/` are generic drawings, not the official AWS Architecture Icons.
