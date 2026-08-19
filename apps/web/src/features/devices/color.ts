export function hsvToHex(hue: number | null, saturation: number | null, value = 100): string {
  if (hue === null || saturation === null) return "#ffffff";
  const normalizedHue = ((hue % 360) + 360) % 360;
  const normalizedSaturation = Math.min(100, Math.max(0, saturation)) / 100;
  const normalizedValue = Math.min(100, Math.max(0, value)) / 100;
  const chroma = normalizedValue * normalizedSaturation;
  const section = normalizedHue / 60;
  const secondary = chroma * (1 - Math.abs(section % 2 - 1));
  const [red, green, blue] = section < 1 ? [chroma, secondary, 0]
    : section < 2 ? [secondary, chroma, 0]
      : section < 3 ? [0, chroma, secondary]
        : section < 4 ? [0, secondary, chroma]
          : section < 5 ? [secondary, 0, chroma]
            : [chroma, 0, secondary];
  const offset = normalizedValue - chroma;
  return `#${[red, green, blue].map((channel) => Math.round((channel + offset) * 255).toString(16).padStart(2, "0")).join("")}`;
}
