import Image from "next/image";

export function BrandAsset({ variant, priority = false }: { variant: "wordmark" | "mark"; priority?: boolean }) {
  const isWordmark = variant === "wordmark";
  const width = isWordmark ? 195 : 52;
  const height = isWordmark ? 45 : 52;
  const prefix = isWordmark ? "kyrion" : "k";
  return <span className={`brand-asset brand-asset-${variant}`}>
    <Image className="brand-asset-light" src={`/branding/${prefix}-light.svg`} alt="Kyrion" width={width} height={height} priority={priority} />
    <Image className="brand-asset-dark" src={`/branding/${prefix}-dark.svg`} alt="Kyrion" width={width} height={height} priority={priority} />
  </span>;
}
