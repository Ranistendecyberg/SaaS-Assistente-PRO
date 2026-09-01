const fs = require("fs");

const source = fs.readFileSync("src/ui/screens/extraction_screen.py", "utf8");

for (const name of ["script_filtros_tsi", "script_filtros"]) {
  const marker = `${name} = \"\"\"`;
  const start = source.indexOf(marker);
  if (start < 0) throw new Error(`Script não encontrado: ${name}`);
  const bodyStart = start + marker.length;
  const end = source.indexOf('"""', bodyStart);
  if (end < 0) throw new Error(`Fim do script não encontrado: ${name}`);
  const javascript = source.slice(bodyStart, end).replaceAll("FULL_HISTORY_FLAG", "true");
  new Function(javascript);
  process.stdout.write(`${name}: JS OK\n`);
}
