#!/usr/bin/env bash
# dist/ çıktısını GitHub Release olarak yayınlar.
#
#   scripts/release.sh            # tag: v{schemaVersion}-{exportedAt tarihi}
#   scripts/release.sh --dry-run  # yalnız ne yapılacağını yazdır
#   scripts/release.sh --cikmis   # nos.db değişmeden yalnız dist/cikmis.json'ı
#                                 # son (latest) release'e yükle/değiştir
#   scripts/release.sh --cikmis --dry-run
#
# dist/cikmis.json (çıkmış soru dizini; pipeline/cikmis/paketle) varsa yeni
# release'e de eklenir. Uygulama onu releases/latest/download/cikmis.json'dan alır.
#
# Kapılar: dist/validation_report.md "PASS" içermeli; dist/nos.db sha256'sı
# meta.sha256_db ile eşleşmeli; aynı tag daha önce yayınlanmamış olmalı.
# Sonunda tüketiciler (nos-academy, nostercih) için nos-data.json pin içeriğini basar.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"
REPO="emrbli/nos-data"
DRY_RUN=0
CIKMIS_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --cikmis) CIKMIS_ONLY=1 ;;
    *) echo "release HATA: bilinmeyen argüman $arg" >&2; exit 1 ;;
  esac
done

die() { echo "release HATA: $*" >&2; exit 1; }

if [[ $CIKMIS_ONLY -eq 1 ]]; then
  CIKMIS="$DIST/cikmis.json"
  [[ -f "$CIKMIS" ]] || die "dist/cikmis.json yok — önce 'uv run --with pypdf python -m pipeline.cikmis.paketle'."
  python3 -c "import json,sys;d=json.load(open(sys.argv[1]));assert d['sorular'] and d['belgeler']" "$CIKMIS" \
    || die "dist/cikmis.json geçersiz (sorular/belgeler boş ya da JSON bozuk)."
  TAG=$(gh release view --repo "$REPO" --json tagName -q .tagName) || die "latest release bulunamadı."
  SHA=$(shasum -a 256 "$CIKMIS" | cut -d' ' -f1)
  echo "tag:    $TAG (latest; nos.db değişmez)"
  echo "dosya:  cikmis.json sha256 $SHA"
  if [[ $DRY_RUN -eq 1 ]]; then echo "(dry-run, yüklenmedi)"; exit 0; fi
  gh release upload "$TAG" "$CIKMIS" --repo "$REPO" --clobber
  echo
  echo "Yüklendi: https://github.com/$REPO/releases/latest/download/cikmis.json"
  echo "Pin için: \"sha256_cikmis\": \"$SHA\" (tag $TAG)"
  exit 0
fi

for f in nos.db meta.json fold_fixture.json validation_report.md programs.json; do
  [[ -f "$DIST/$f" ]] || die "dist/$f yok — önce 'uv run python run.py' koşun."
done
grep -q "PASS" "$DIST/validation_report.md" || die "validation_report.md PASS içermiyor; yayınlanmaz."

SCHEMA=$(python3 -c "import json;print(json.load(open('$DIST/meta.json'))['schemaVersion'])")
EXPORTED=$(python3 -c "import json;print(json.load(open('$DIST/meta.json'))['exportedAt'])")
META_SHA=$(python3 -c "import json;print(json.load(open('$DIST/meta.json'))['sha256_db'])")
COUNT=$(python3 -c "import json;print(json.load(open('$DIST/meta.json'))['programCount'])")
FILE_SHA=$(shasum -a 256 "$DIST/nos.db" | cut -d' ' -f1)
[[ "$FILE_SHA" == "$META_SHA" ]] || die "dist/nos.db sha256 ($FILE_SHA) meta.sha256_db ($META_SHA) ile uyuşmuyor."

TAG="v${SCHEMA}-${EXPORTED:0:10}"
TITLE="nos.db ${EXPORTED:0:10} (şema v${SCHEMA}, ${COUNT} program)"

if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  die "$TAG zaten yayınlanmış. Yeni veri için pipeline'ı yeniden koşun (exportedAt değişir)."
fi

echo "tag:    $TAG"
echo "title:  $TITLE"
echo "sha256: $META_SHA"
if [[ $DRY_RUN -eq 1 ]]; then echo "(dry-run, release oluşturulmadı)"; exit 0; fi

ASSETS=("$DIST/nos.db" "$DIST/meta.json" "$DIST/fold_fixture.json"
        "$DIST/validation_report.md" "$DIST/programs.json")
[[ -f "$DIST/cikmis.json" ]] && ASSETS+=("$DIST/cikmis.json")

gh release create "$TAG" "${ASSETS[@]}" \
  --repo "$REPO" --title "$TITLE" --notes-file "$DIST/validation_report.md" --latest

cat <<PIN

Release hazır: https://github.com/$REPO/releases/tag/$TAG

Tüketicilerde nos-data.json:
{
  "repo": "$REPO",
  "tag": "$TAG",
  "schemaVersion": $SCHEMA,
  "sha256_db": "$META_SHA"
}
PIN
