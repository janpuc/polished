# Changelog

## [0.5.0](https://github.com/janpuc/polished/compare/v0.4.0...v0.5.0) (2026-10-26)


### Features

* **api:** /api/v1 read endpoints, per-device tokens with the app's PKCE sign-in, apple-app-site-association, UI-test reset ([c6a7475](https://github.com/janpuc/polished/commit/c6a747550997293a0e439b8466673cce93b9d6c9))
* v3 web look (lit tips, Fraunces display roles, warm palette, level arc, date field), /api/v1 writes, wear log, https sign-in callback for the app ([9a0fde3](https://github.com/janpuc/polished/commit/9a0fde377263e9d09c40c2a42cf22982ac0cf9e9))


### Documentation

* native app spec (SwiftUI for iPhone, iPad and iPhone Duo, /api/v1 contract, tip renderer port, TestFlight) ([e6fad41](https://github.com/janpuc/polished/commit/e6fad417747dd671ce1b3d4dfe8ab768365aac9c))
* native target iOS 27.1, App Store Connect name and API key location ([07e5285](https://github.com/janpuc/polished/commit/07e5285fd1993092caeddeb8f4685659993d0b62))

## [0.4.0](https://github.com/janpuc/polished/compare/v0.3.0...v0.4.0) (2026-10-26)


### Features

* fuzzy search with ranked tiers and highlighted matches, delete a wheel with confirmation, observable e2e flows on iPhone, iPad and Mac ([eba80f2](https://github.com/janpuc/polished/commit/eba80f26d398e300410749bf886125d8173a11cb))


### Documentation

* design reference research ([1c63d44](https://github.com/janpuc/polished/commit/1c63d44f5ad89e235344a510cd1f07e1b9ba5333))
* NFC writing, Holo Taco wishlist and iOS date input research ([8cd0718](https://github.com/janpuc/polished/commit/8cd071840790bf54a668571ce37bdd0a91d4150a))
* roadmap (phases 1-3) and the v3 web design spec ([b486225](https://github.com/janpuc/polished/commit/b486225244c0896350b61d3d1e1a40c60bdcc57f))

## [0.3.0](https://github.com/janpuc/polished/compare/v0.2.0...v0.3.0) (2026-10-26)


### Features

* Holo Taco's official release list (release dates, collections, retired flags, shades the shop no longer lists) ([3ff35c5](https://github.com/janpuc/polished/commit/3ff35c5ebee02962d9ad159697a23d57e7ffb858))


### Bug Fixes

* keep the sign-in callback's code and state out of the access log ([f3bd1aa](https://github.com/janpuc/polished/commit/f3bd1aace8b12d8f2ac00afe15f3905a9137da1e))

## [0.2.0](https://github.com/janpuc/polished/compare/v0.1.0...v0.2.0) (2026-10-25)


### Features

* barcode scanner (zxing-wasm), learned barcode and P-code lookup (stage 5) ([0f4afff](https://github.com/janpuc/polished/commit/0f4afff911f690111310fd1192ee54bf3f4c9f4e))
* bottles, wishlist with Holo Taco checkout link, manual shades (stage 4) ([4249cb1](https://github.com/janpuc/polished/commit/4249cb1cd2d4db4e6c26dd2935613854be04e23f))
* browse, search, filters, shade pages and the PWA shell (stage 3) ([511e41b](https://github.com/janpuc/polished/commit/511e41b0a6e43024ead9826434bc287e6a50cc16))
* catalog sync from holotaco.com with classification, aliases and absence rules (stage 2) ([c0c4f88](https://github.com/janpuc/polished/commit/c0c4f88841f7260f919bc2d708fc4fd84f9a9282))
* generated painted-nail tips from sampled polish colour and finish, layered composites, tip colour override ([4698d4d](https://github.com/janpuc/polished/commit/4698d4d5e19cecb728dffc0e97c6164af657ac61))
* layer-stack builder sheet with live summary, templates and picker (stage 7 UI) ([2b5bac7](https://github.com/janpuc/polished/commit/2b5bac7b40574cd9b3ee95e7aacea23322405032))
* logo v2, a foil-painted nail on a fingertip ([1f4aadb](https://github.com/janpuc/polished/commit/1f4aadbdde6635c370d51ef4f5dd7e98f6bad712))
* painted-nail swatch photos on wheel tips, final visual polish from the design review ([8dfb6f9](https://github.com/janpuc/polished/commit/8dfb6f90e9e15c7ab58d549962c6c208c51216da))
* purchase history by month and year, 'I bought these' from the wishlist ([1e5bc05](https://github.com/janpuc/polished/commit/1e5bc053814f2a817d43a52a45e0dbb6995525f0))
* skeleton, migrations, Pocket ID sign-in and deny-by-default gate (stage 1) ([14e0368](https://github.com/janpuc/polished/commit/14e0368ba7cd0f41c82daf6017d5141f78d7a6cd))
* swatch book look, run 1 (ink and board palette, system type, tips in every list, ring on a hairline) ([6dcb6d3](https://github.com/janpuc/polished/commit/6dcb6d3ed89e8c86f2054044c9a230831d5b8e17))
* swatch book run 2a (bottle rows with level glyphs, short wishlist head, builder head with the composite tip) ([fe6fe5f](https://github.com/janpuc/polished/commit/fe6fe5f73c7cd0b60b250b56470140aef050c8c9))
* swatch book run 2b (home with the last wheel, mini rings, tip beside the shade title, camera-first scan, More page, VISUAL.md rewritten) ([1ca700c](https://github.com/janpuc/polished/commit/1ca700cffb51fd159fd90852175fac6958f9e706))
* swatch wheel pages with the nail-tip ring, tag and QR page, swatched-on links (stage 6 UI) ([29a7f58](https://github.com/janpuc/polished/commit/29a7f58d1c89cf793cc5cdbaf993b74378463e35))
* visual redesign (pearl and plum, Fraunces, tab bar, sheet motion) and the nail-tip logo ([dc698f4](https://github.com/janpuc/polished/commit/dc698f446dfa1231678daa799a64d30fbbd2f989))
* wheels and layer-stack domain logic with slugs, QR and drafts (stages 6-7 backend) ([0f6bf73](https://github.com/janpuc/polished/commit/0f6bf7304c6b7b451433969fafb0701bacec00cf))


### Bug Fixes

* a clear topper adds no tint of its own, softer holo sheen on toppers ([f31eedb](https://github.com/janpuc/polished/commit/f31eedb6ebaf0e119c302f995adaf9481df8a1c9))
* colour sampling rejects skin and dark backdrops, sheer base coats, checked colours for five shades, colours CLI ([5f3fb28](https://github.com/janpuc/polished/commit/5f3fb28b0dda0cc663ab1c5b075557a8d54ec35c))
* fold the shop's 'whte' colour tag into white; docs: README status and deploy section ([c57babd](https://github.com/janpuc/polished/commit/c57babde26d9a4f0a6b6954af1ba6ff4df63e911))
* require a validated ID token for our audience, bind userinfo to its sub, loopback-only dev mode ([a2a6657](https://github.com/janpuc/polished/commit/a2a665797bb51533f407604ccbb33a4b1aca6201))


### Documentation

* brief, design advice, v1 design and build plan ([cc2df80](https://github.com/janpuc/polished/commit/cc2df805c9894f14bca048238cb7015aea8ba395))
* colour sampling rules ([9312007](https://github.com/janpuc/polished/commit/9312007a89e80bdd524bdfe3fc50d78753ae6846))
* deploy guide matches the 0.2.0 release and the first colour read ([a788139](https://github.com/janpuc/polished/commit/a78813942b206e370afc197500f9a5daf3d1b2cd))
* swatch book design direction ([d07b613](https://github.com/janpuc/polished/commit/d07b6136e42b6239911b9c5a0cdef37e0bb4f707))
* visual design plan (pearl gallery, nail-tip wheel, logo) ([058b46e](https://github.com/janpuc/polished/commit/058b46ef05626e7051b6c531b86d5ba2fc27189e))


### Build & CI

* container image, CI and release workflows, home-ops manifests and deploy guide (stage 8) ([03af94e](https://github.com/janpuc/polished/commit/03af94ea359b8cc9c4192ecd6169ce7d96471b28))
