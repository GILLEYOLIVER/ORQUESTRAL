import { describe, expect, it } from "vitest";
import {
  coerceMetadataInput,
  displayMetadataValue,
  inputTypeForMetadataField,
} from "./valueCoercion";

describe("runtime de formularios por metadados", () => {
  it("converte inteiros, decimais e booleanos sem perder o contrato", () => {
    expect(coerceMetadataInput("integer", "42")).toBe(42);
    expect(coerceMetadataInput("decimal", "19.90")).toBe("19.90");
    expect(coerceMetadataInput("boolean", true)).toBe(true);
  });

  it("omite campos vazios e interpreta JSON valido", () => {
    expect(coerceMetadataInput("text", "  ")).toBeUndefined();
    expect(coerceMetadataInput("json", '{"ativo":true}')).toEqual({
      ativo: true,
    });
  });

  it("seleciona controles e rotulos compreensiveis", () => {
    expect(inputTypeForMetadataField("email")).toBe("email");
    expect(inputTypeForMetadataField("date")).toBe("date");
    expect(displayMetadataValue(false)).toBe("Não");
  });
});
