# Ciclo 102 - Catálogo comercial, variantes e promoções

O módulo Comércio e receita reutiliza os produtos físicos do Estoque e as
tabelas publicadas do CRM. Ele adiciona variantes, promoções com ciclo de vida
e resolução determinística de preço pela regra de maior desconto elegível.

As tabelas são isoladas por empresa com RLS forçado. A API valida produto,
variante, vigência, quantidade mínima, limite de usos e código promocional.
Nenhum preço é aceito diretamente do navegador.
