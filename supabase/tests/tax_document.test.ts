import { validCpf, validCnpj, validDocument } from "../functions/_shared/v2.ts";

Deno.test("CPF/CNPJ checksums and formatted documents", () => {
  for (const value of ["52998224725", "529.982.247-25", "11222333000181", "11.222.333/0001-81"]) {
    if (!validDocument(value)) throw new Error("Valid test document rejected");
  }
  for (const value of [null, "", "11111111111", "52998224724", "11222333000182", "123", "５２９９８２２４７２５"]) {
    if (validDocument(value)) throw new Error("Invalid test document accepted");
  }
  if (validCpf("11222333000181") || validCnpj("52998224725")) throw new Error("Wrong document type");
});
