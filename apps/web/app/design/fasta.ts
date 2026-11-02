export type FastaTarget = {
  gene_id: string;
  description: string;
  sequence_rna: string;
};

export type FastaParseResult = {
  targets: FastaTarget[];
  error: string | null;
};

const idPattern = /^[A-Za-z][A-Za-z0-9_.-]{0,63}$/;

export function parseMultiFasta(input: string): FastaParseResult {
  if (!input.trim()) return { targets: [], error: null };

  const targets: FastaTarget[] = [];
  let current: { gene_id: string; description: string; sequence: string[]; line: number } | null = null;
  const finish = (): string | null => {
    if (!current) return null;
    const sequenceDna = current.sequence.join("").toUpperCase();
    if (!sequenceDna) return `El gen ${current.gene_id} no tiene secuencia.`;
    if (/[^ACGTU]/.test(sequenceDna)) return `El gen ${current.gene_id} contiene un carácter inválido; sólo se admite A, C, G, T o U.`;
    if (sequenceDna.length < 21) return `La secuencia de ${current.gene_id} tiene ${sequenceDna.length} nt; se necesitan al menos 21.`;
    targets.push({ gene_id: current.gene_id, description: current.description, sequence_rna: sequenceDna.replaceAll("T", "U") });
    return null;
  };

  const lines = input.replace(/^\uFEFF/, "").split(/\r?\n/);
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].trim();
    if (!line) continue;
    if (line.startsWith(">")) {
      const previousLine = current?.line;
      const previousError = finish();
      if (previousError) return { targets: [], error: `Línea ${previousLine}: ${previousError}` };
      const header = line.slice(1).trim();
      const separator = header.search(/\s/);
      const geneId = separator < 0 ? header : header.slice(0, separator);
      const description = separator < 0 ? "" : header.slice(separator).trim();
      if (!geneId) return { targets: [], error: `Línea ${index + 1}: el encabezado FASTA necesita un identificador después de >.` };
      if (!idPattern.test(geneId)) return { targets: [], error: `Línea ${index + 1}: el ID ${geneId} no tiene un formato válido.` };
      if (targets.some((target) => target.gene_id === geneId)) {
        return { targets: [], error: `ID repetido: ${geneId}. Cada gen necesita un identificador único.` };
      }
      if (targets.length >= 8) return { targets: [], error: "Se admiten entre 2 y 8 genes objetivo." };
      current = { gene_id: geneId, description, sequence: [], line: index + 1 };
      continue;
    }
    if (!current) return { targets: [], error: `Línea ${index + 1}: hay secuencia antes del primer encabezado FASTA (>).` };
    current.sequence.push(line.replace(/\s/g, ""));
  }

  const finalError = finish();
  if (finalError) return { targets: [], error: `Línea ${current?.line}: ${finalError}` };
  if (targets.length < 2) return { targets: [], error: "Pegá entre 2 y 8 genes en formato multi-FASTA." };
  if (targets.length > 8) return { targets: [], error: "Se admiten entre 2 y 8 genes objetivo." };
  if (targets.reduce((total, target) => total + target.sequence_rna.length, 0) > 20_000) {
    return { targets: [], error: "Las secuencias suman más de 20.000 nt; reducí la cantidad o longitud de las secuencias." };
  }
  return { targets, error: null };
}
