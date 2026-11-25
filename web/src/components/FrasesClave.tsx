import type { Frase } from "@/lib/tipos";

export function FrasesClave({ frases }: { frases: Frase[] }) {
  return (
    <section aria-labelledby="t-frases">
      <h2 id="t-frases" className="font-display text-2xl font-semibold">Tres datos para entender el momento</h2>
      <ol className="mt-5 grid gap-5 md:grid-cols-3">
        {frases.map((f, i) => (
          <li key={f.origen} className="flex gap-4 border-t-2 pt-4" style={{ borderColor: "var(--acento)" }}>
            <span aria-hidden className="cifra font-display text-3xl font-semibold text-tinta-2">{i + 1}</span>
            <div className="min-w-0">
              <p className="leading-relaxed">{f.texto}</p>
              <p className="mt-2 break-all font-mono text-[11px] text-tinta-2">Gold: {f.origen}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
