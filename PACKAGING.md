# Packaging and store submission

**Author / credit:** Ranga Seshadri \<rangabb@gmail.com\>  
**Upstream:** https://github.com/ranga291257/easydraw  
**License:** MIT (`LICENSE`)

This tree ships packaging helpers under `packaging/`. Omarchy and the community store only list apps that install via **pacman / AUR / Omarchy packages** — not a zip from GitHub alone. The GitHub repository must stay **public** so PKGBUILD sources and store metadata can fetch releases.

## 1. Release (upstream)

Tagged releases drive the PKGBUILD source URL:

```sh
git tag -a v1.0.0 -m "EasyDraw 1.0.0"
git push origin v1.0.0
gh release create v1.0.0 --title "EasyDraw 1.0.0" --notes "First packaged release."
```

Then fill checksums:

```sh
cd packaging
updpkgsums   # or: curl -sL …/v1.0.0.tar.gz | sha256sum
```

Commit the updated `sha256sums` in `packaging/PKGBUILD`.

## 2. AUR (recommended first)

1. Create an [AUR account](https://aur.archlinux.org/) and add an SSH key.
2. `git clone ssh://aur@aur.archlinux.org/easydraw.git`
3. Copy `packaging/PKGBUILD` into that repo; run `makepkg --printsrcinfo > .SRCINFO`.
4. Commit and `git push` to the AUR.
5. Test: `yay -S easydraw` (or `makepkg -si` locally).

Keep `Maintainer: Ranga Seshadri <rangabb@gmail.com>` for credit.

## 3. Official Omarchy packages

Fork [omacom/omarchy-pkgs](https://github.com/omacom/omarchy-pkgs), then:

```sh
bin/add-package easydraw --local --scaffold
```

Replace the scaffold with this project’s `packaging/PKGBUILD` (adapted to their layout) and put `packaging/omarchy-package.json` at `pkgbuilds/easydraw/.omarchy/package.json`. Open a PR against `master` describing the app, author credit, and how you tested (`makepkg` / install / launcher).

Guide: https://omarchyapps.com/develop.html

## 4. Community Omarchy Store

After the package exists on the **AUR** (or in Omarchy pacman repos), fork [omarchy-community/store](https://github.com/omarchy-community/store) and add:

`registry/apps/easydraw.json` ← contents of `packaging/store-easydraw.json`

If Omarchy ships it under a different install method, change `install` to `"method": "pacman"` or `"method": "omarchy"` as appropriate. Open a PR per their CONTRIBUTING.md.

## Local package test

```sh
cd packaging
makepkg -si
easydraw
```

Uninstall with `sudo pacman -Rns easydraw`.
