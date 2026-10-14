import type { Guide } from "@/types/learning";

export function downloadGuide(guide: Guide) {
  const refs = guide.sources
    .filter((s) => guide.citations.includes(s.id))
    .map((s) => `${s.document} (${s.page})\n${s.text}`)
    .join("\n\n");
  const url = URL.createObjectURL(
    new Blob([`${guide.content}\n\nSources\n${refs}`], {
      type: "text/markdown;charset=utf-8",
    }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = "stride-guide.md";
  link.click();
  URL.revokeObjectURL(url);
}
