import { copyFile, mkdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

// Root SVGs remain the only tracked source. Deployment copies are disposable.
const source = new URL("../../../branding/", import.meta.url);
const output = new URL("../public/branding/", import.meta.url);
await mkdir(output, { recursive: true });
for (const name of ["k-light", "k-dark", "kyrion-light", "kyrion-dark"]) {
  await copyFile(
    new URL(`logo/${name}.svg`, source),
    new URL(`${name}.svg`, output),
  );
}
await copyFile(
  new URL("favicon/favicon.svg", source),
  new URL("favicon.svg", output),
);
await sharp(await readFile(new URL("icons/app-light.svg", source)))
  .resize(180, 180)
  .png()
  .toFile(fileURLToPath(new URL("apple-touch-icon.png", output)));

// Social SVGs are currently empty placeholders. Compose the baseline from the
// approved wordmark without redrawing or modifying its geometry.
const wordmark = await sharp(
  await readFile(new URL("logo/kyrion-dark.svg", source)),
)
  .resize(780, 180)
  .png()
  .toBuffer();
await sharp({
  create: { width: 1200, height: 630, channels: 4, background: "#0B1421" },
})
  .composite([{ input: wordmark, left: 210, top: 225 }])
  .png()
  .toFile(fileURLToPath(new URL("og-image.png", output)));
