# Test fixtures

`feed_trimmed.json` is a `/products.json` page of 16 real Holo Taco products reduced to catalog
fields: id, title, handle, `published_at`, `updated_at`, product type, tags, one variant (id,
SKU, price, `compare_at_price`, availability, position) and the first two images. There is no
`body_html`. Tests feed it to the sync through `httpx.MockTransport` or `apply_feed`; nothing
here is fetched from the shop at test time.

Regenerate it from the untracked local snapshot (`research/p1.json` to `p3.json`) with

```sh
python3 -I scripts/make_fixtures.py
```

| Handle | Why it is here |
|---|---|
| `thirst-trap` | normal `HL-*-NP` polish with finish and colour tags, in stock |
| `thirst-trap-birthday-gift` | gift that merges onto `thirst-trap` by handle |
| `gold-play-button` | older `HLT-NP-*` polish, retired and sold out |
| `hit-the-lights` | sold out, not retired |
| `jam-session` | soon-retiring and sold out |
| `rest-in-peach` | soon-retiring, in stock; **its `compare_at_price` is raised to 16.50 by the script** because no single shade is on sale in the real feed (price 13.50) |
| `aurora-unicorn-skin` | Top Coat, so a topper |
| `aurora-unicorn-skin-birthday-gift` | gift that merges onto a Top Coat by handle |
| `peely-base` | Base Coat |
| `sticky-base` | polish tagged `color:clear`, so a topper |
| `brainrot-collection` | bundle (`bundle:product`) |
| `coastal-cremes-collection` | bundle whose only bundle tag is `bundles-sets` |
| `royal-tea-blue-2021` | target of a manual alias |
| `royal-tea-blue-birthday-gift` | gift that needs the manual alias |
| `linear-holo-taco™-birthday-gift` | manual-alias gift whose shade is not in the fixture: stays unresolved |
| `super-magnet` | accessory, skipped |

Expected roles: 9 shades (7 polish, 1 topcoat, 1 basecoat), 2 bundles, 4 aliases (3 resolve),
1 skipped.
