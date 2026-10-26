const TITLES = new Set(["dr", "dr.", "prof", "prof.", "mr", "mr.", "ms", "ms.", "mrs", "mrs."]);

/** How to greet someone: "Nikita" for "Nikita Singh", "Dr. Sharma" for "Dr. Anita Sharma". */
export function greetName(full: string | undefined): string {
  const parts = (full ?? "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "";
  if (TITLES.has(parts[0].toLowerCase()) && parts.length > 1) return `${parts[0]} ${parts[parts.length - 1]}`;
  return parts[0];
}
