## VV Generator v1.7.0

**EN** — Performance and quality release, informed by the existing Fusion 360 Voronoi tools.
- **2.3x to 3.4x faster** generation (Bridson Poisson-disk seeding instead of random darts, cached spatial queries, inlined hot loops) with identical wall / coverage guarantees. Typical faces: 0.4 to 1.7 s.
- **Lloyd relaxation** (new "Relaxation" field, default 3 steps): cell-size variation drops about 25-35 %.
- **Your own seed points** (select sketch points, optionally "Use only my points").
- **Preview** checkbox (runs the real build inside Fusion's preview, then Fusion rolls it back).
- Better gap filling near concave outlines (residual uncovered area on an irregular test face: 0.42 % -> 0.01 %).
- Report now also shows cell-size variation, seed points used and generation time. Clear warning when "only my points" leaves regions solid.
- Tests: 20 engine tests + 16 glue tests; ~550 random irregular cases without a single invariant violation.

**PT-BR** — Versão de desempenho e qualidade, com base nas ferramentas de Voronoi que já existem para o Fusion 360.
- Geração **2,3x a 3,4x mais rápida** (amostragem de Poisson de Bridson no lugar de dardos aleatórios, consultas espaciais com cache, laços quentes otimizados), com as mesmas garantias de parede e cobertura. Faces típicas: 0,4 a 1,7 s.
- **Relaxamento de Lloyd** (novo campo "Relaxamento", padrão 3 passos): a variação de tamanho das células cai cerca de 25-35 %.
- **Seus próprios pontos de semente** (selecione pontos de esboço, com a opção "Usar somente meus pontos").
- Caixa **Pré-visualizar** (executa a geração real na pré-visualização do Fusion, que depois é desfeita).
- Melhor preenchimento de lacunas perto de contornos côncavos (área sem padrão numa face irregular de teste: 0,42 % -> 0,01 %).
- O relatório agora mostra também a variação de tamanho das células, os pontos de semente usados e o tempo de geração. Aviso claro quando "somente meus pontos" deixa regiões sólidas.
- Testes: 20 do motor + 16 da camada do Fusion; cerca de 550 casos aleatórios irregulares sem nenhuma violação de invariante.

**ES** — Versión de rendimiento y calidad, basada en las herramientas de Voronoi que ya existen para Fusion 360.
- Generación **2,3x a 3,4x más rápida** (muestreo de Poisson de Bridson en lugar de dardos aleatorios, consultas espaciales con caché, bucles críticos optimizados), con las mismas garantías de pared y cobertura. Caras típicas: 0,4 a 1,7 s.
- **Relajación de Lloyd** (nuevo campo "Relajación", 3 pasos por defecto): la variación de tamaño de las celdas baja entre un 25 y un 35 %.
- **Sus propios puntos semilla** (seleccione puntos de boceto, con la opción "Usar solo mis puntos").
- Casilla **Vista previa** (ejecuta la generación real en la vista previa de Fusion, que luego se deshace).
- Mejor relleno de huecos cerca de contornos cóncavos (área sin patrón en una cara irregular de prueba: 0,42 % -> 0,01 %).
- El informe ahora muestra también la variación de tamaño de celdas, los puntos semilla usados y el tiempo de generación. Aviso claro cuando "solo mis puntos" deja regiones sólidas.
- Pruebas: 20 del motor + 16 de la capa de Fusion; unos 550 casos aleatorios irregulares sin ninguna violación de invariante.

---


**EN** — Full review and hardening release.
- New geometry engine (separate, unit-tested module). Cells are trimmed with supporting half-planes of capsules around the outline and of the keep-out discs, so the pattern never crosses the solid rim — also on concave, irregular or imprecise faces.
- Automatic gap filling for Voronoi / circles; refusal (with explanation) when the requested size cannot fit the cell limit instead of a partial pattern.
- **Analysis report** after every run: face and outline data, reinforcement found, shape count and sizes, reinforced vs light zone, measured minimum wall, open area, coverage / largest gap, volume and mass removed.
- Dialog and messages follow Fusion's language (English, Português-BR, Español); live validation disables OK on invalid input.
- **Toolbar icon fixed/redone** (transparent 16/32/64 px, light and dark), icon folder path in the format used by Autodesk's template.
- Robustness: native-component handling, timeline group, automatic cleanup of the sketch on failure, per-shape draw isolation, reinforcement from other components ignored with a warning, inner fillets no longer treated as holes.
- Tests: 15 engine tests (brute-force oracle, irregular outlines, fuzz) + 11 glue tests; ~285 extra random stress cases ran without a single invariant violation.

**PT-BR** — Versão de revisão completa e endurecimento.
- Novo motor geométrico (módulo separado e testado). As células são aparadas com semiplanos de suporte de cápsulas ao redor do contorno e das zonas protegidas; o padrão nunca cruza a borda sólida, também em faces côncavas, irregulares ou imprecisas.
- Preenchimento automático de lacunas (Voronoi / círculos); recusa explicada quando o tamanho pedido não cabe no limite de células, em vez de um padrão parcial.
- **Relatório de análise** a cada execução: dados da face e do contorno, reforços encontrados, formas e tamanhos, zona reforçada x leve, parede mínima medida, área aberta, cobertura / maior lacuna, volume e massa removidos.
- Janela e mensagens seguem o idioma do Fusion (inglês, português-BR, espanhol); validação em tempo real desabilita o OK com entrada inválida.
- **Ícone da barra refeito** (transparente 16/32/64 px, claro e escuro), caminho da pasta de ícones no formato do template da Autodesk.
- Robustez: tratamento de componente nativo, grupo na linha do tempo, limpeza automática do esboço em caso de falha, isolamento de erro por forma, reforços de outros componentes ignorados com aviso, raios internos não são mais tratados como furos.
- Testes: 15 do motor (oráculo por força bruta, contornos irregulares, fuzz) + 11 da camada do Fusion; cerca de 285 casos aleatórios extras sem nenhuma violação.

**ES** — Versión de revisión completa y endurecimiento.
- Nuevo motor geométrico (módulo separado y probado). Las celdas se recortan con semiplanos de soporte de cápsulas alrededor del contorno y de las zonas protegidas; el patrón nunca cruza el borde sólido, también en caras cóncavas, irregulares o imprecisas.
- Relleno automático de huecos (Voronoi / círculos); rechazo explicado cuando el tamaño pedido no cabe en el límite de celdas, en vez de un patrón parcial.
- **Informe de análisis** en cada ejecución: datos de la cara y del contorno, refuerzos encontrados, formas y tamaños, zona reforzada vs ligera, pared mínima medida, área abierta, cobertura / mayor hueco, volumen y masa retirados.
- Ventana y mensajes siguen el idioma de Fusion (inglés, portugués-BR, español); la validación en vivo deshabilita OK con entradas inválidas.
- **Icono de la barra rehecho** (transparente 16/32/64 px, claro y oscuro), ruta de la carpeta de iconos en el formato de la plantilla de Autodesk.
- Robustez: manejo de componente nativo, grupo en la línea de tiempo, limpieza automática del boceto ante fallos, aislamiento de errores por forma, refuerzos de otros componentes ignorados con aviso, radios internos ya no se tratan como agujeros.
- Pruebas: 15 del motor (oráculo por fuerza bruta, contornos irregulares, fuzz) + 11 de la capa de Fusion; unos 285 casos aleatorios extra sin ninguna violación.

Limitations / Limitações / Limitaciones: planar faces only · geometric analysis, not FEA · not parametric · validate in Fusion on a copy of the part.
