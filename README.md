<p align="center">
  <img src="assets/images/LOGO FLASHBIO.png" width="250" alt="FlashBio Logo">
</p>

<h1 align="center">VV Generator</h1>

<p align="center">
  <em>Adaptive lightweight patterns for Autodesk Fusion 360</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.7.0--beta-orange.svg?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/Status-Beta%20Testing-red.svg?style=flat-square" alt="Status">
  <img src="https://img.shields.io/badge/AI-Powered-blue.svg?style=flat-square" alt="AI Powered">
  <img src="https://img.shields.io/badge/Autodesk-Fusion%20360-0696D7.svg?style=flat-square&logo=autodesk" alt="Fusion 360">
</p>

<br>

> [!WARNING]
> **⚠️ BETA STATUS AND AI USAGE WARNING**
> This project utilizes **Artificial Intelligence** in its development and is currently in **BETA TESTING** phase. The software may present instabilities, generate unexpected behaviors, or cause issues in your Fusion 360 project.
> **USE AT YOUR OWN RISK.** Always back up your files before applying the script and validate structural performance with simulations.

---

## 🌐 Documentation / Documentação / Documentación

This document is available in three languages. Expand the section you need below.
*Este documento está disponível em três idiomas. Expanda a seção desejada abaixo.*
*Este documento está disponible en tres idiomas. Expanda la sección que necesite a continuación.*

<details>
<summary><h2>🇺🇸 Part I — English</h2></summary>

### 1. Overview
VV Generator is a Python add-in for Autodesk Fusion 360 that generates lightweight cut-out patterns on a planar face of a solid body. It draws the pattern in a new sketch and, in the same command, cuts it through the body with an Extrude (Cut) feature.

**What it does:**
- Reads the selected face and the holes of the body to decide where structure is needed.
- Makes the pattern adaptive: more material around holes and selected reinforcement faces, lighter areas farther away.
- Keeps a solid rim along the outline of the face and a solid zone around holes — also on concave, irregular or imprecise faces.
- Offers five formats: Voronoi (sharp corners), Voronoi (rounded corners), honeycomb hexagons, triangular mesh and circles.
- **Lloyd relaxation** evens out the cell sizes (Voronoi and circles).
- Lets you place your **own seed points** (sketch points) and, optionally, use only those points.
- Has an optional **live preview** (off by default).
- Shows a **measured analysis report** after every run (see section 5).
- The dialog, messages and report follow Fusion's language (English, Português-BR or Español).

### 2. Requirements and Installation
**Requirements:** Autodesk Fusion 360 desktop (Windows or macOS), Design workspace. No external libraries needed.

**Option A — release package (recommended):**
1. Download `VVGenerator-v1.7.0.zip` from the **Releases** page and unzip it.
2. Run `install-windows.bat` (Windows) or `install-macos.command` (macOS).

**Option B — manual:** copy the whole `VVGenerator` folder (it contains `VVGenerator.py`, `vv_engine.py`, `VVGenerator.manifest` and `resources/`) to the Add-Ins directory:
   - **Win:** `%appdata%\Autodesk\Autodesk Fusion 360\API\AddIns`
   - **Mac:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns`

Then, in Fusion, open **Utilities ▸ Add-Ins** (Shift+S), select **VV Generator** and run it. The button appears in **Solid ▸ Create**.

**Updating:** replace the files, then **Stop** and **Run** the add-in again (restart Fusion once if the toolbar icon looks stale). If you still have the old `VoronoiStructure` folder, delete it to avoid two buttons.

### 3. Quick Start
1. Go to **Solid ▸ Create ▸ VV Generator**.
2. Select the **planar face**.
3. (Optional) Select **reinforcement faces**. Keep *Detect holes automatically* on.
4. (Optional) Select **seed points** from a sketch. Tick *Use only my points* to generate only those cells.
5. Choose the **Shape** and adjust the parameters (defaults are a good first attempt).
6. (Optional) Tick **Preview** to see the result before confirming. It is slower, so it is off by default.
7. Click **OK**. Read the report: it shows what was found and what was removed.

### 4. Main Options
| Option | Applies to | Description |
|---|---|---|
| Shape | All | Voronoi sharp / rounded, hexagons, triangles, circles |
| Corner radius | Rounded, hexagons, triangles | 0 = sharp corners |
| Wall thickness | All | Exact wall (Voronoi), minimum gap (circles), thinnest wall (tilings) |
| Tile side · Wall near reinforcement · Mesh rotation | Hexagons, triangles | Regular mesh; the wall grows near reinforcement |
| Minimum / maximum cell · Transition distance | Voronoi, circles | Cell size near / far from reinforcement |
| Relaxation | Voronoi, circles | Lloyd smoothing steps (default 3, 0 = off) |
| Seed points · Use only my points | Voronoi, circles | Cell centres chosen by you |
| Solid zone around holes · Solid rim | All | Material kept around holes and along the outline |
| Cell limit · Random seed | All | Maximum number of cells · layout variation |
| Depth | All | Through all, or a fixed distance |

### 5. Analysis Report
After each run the add-in shows (and writes to Fusion's log): face area, bounding box and outline length; reinforcement found; number and size of shapes; shapes in the reinforced versus light zone; cell-size variation; measured minimum wall; open area; coverage and largest gap; volume and mass removed; and warnings.
The analysis is **geometric** (proximity to holes and reinforcement). It is **not** finite-element analysis — always validate with a simulation study.

### 6. Limitations
- Planar faces only. The result is not parametric: if the part changes, delete the sketch and the cut and run the command again.
- Geometric analysis, not FEA.
- Narrow necks and sharp inner corners can stay solid; the report warns about it.
- With *Use only my points*, regions far from your points stay solid (a cell is always convex).
- The geometry engine and the Fusion layer are covered by automated tests that run **outside** Fusion. They do not replace validation inside Fusion: test on a copy of your part.

### 7. Update History
| Version | Changes |
|---|---|
| **1.7.0** | 2.3×–3.4× faster generation; **Lloyd relaxation**; **your own seed points** (and "use only my points"); optional **preview**; better gap filling near concave outlines; report shows cell-size variation, seed points used and generation time. |
| **1.6.0** | Full code review. New geometry engine (`vv_engine.py`) that guarantees the pattern never crosses the solid rim, even on concave or imprecise faces; automatic gap filling; **analysis report**; dialog and messages follow Fusion's language; live input validation; new toolbar icons; safer handling of components, failures and clean-up; automated tests. |
| **1.5.0** | True honeycomb and triangular meshes covering the whole face, with a wall that grows near reinforcement; tile side and mesh rotation. |
| **1.4.0** | Shape selector: rounded Voronoi, hexagons, triangles, circles; corner radius. |
| **1.3.0** | Renamed to **VV Generator**; logo and footer in the dialog; diagnostics and batch cutting; filter for tiny cells. |
| **1.2.0** | Robust cut: tries both directions and checks that volume really dropped. |
| **1.1.0** | Straight cells along the outline at a uniform rim; protected zones around reinforcement; extra seeding passes to fill gaps. |
| **1.0.0** | First version: adaptive Voronoi on a planar face, hole detection, sketch and cut. |

### 8. Credits and Support
**Developed by Team Flashbio #31888**
- **Cauã Vioto** — Lead Creator / Principal Developer
- **Gabriel Chidi** — Support / Contributor
- **João Lacerda** — Support / Contributor

When reporting an issue, include the Fusion version, a screenshot, parameter values, and the full text of the message shown by the add-in.
</details>

<details>
<summary><h2>🇧🇷 Parte II — Português (Brasil)</h2></summary>

### 1. Visão Geral
O VV Generator é um add-in em Python para o Autodesk Fusion 360 que gera padrões de corte leves em uma face plana de um corpo sólido. Ele desenha o padrão em um novo esboço e, no mesmo comando, o corta através do corpo com uma extrusão (Corte).

**O que ele faz:**
- Lê a face selecionada e os furos do corpo para decidir onde é necessária estrutura.
- Torna o padrão adaptativo: mais material ao redor de furos e faces de reforço, áreas mais leves e abertas mais longe.
- Mantém uma borda sólida ao longo do contorno e uma zona sólida ao redor dos furos — inclusive em faces côncavas, irregulares ou imprecisas.
- Oferece cinco formatos: Voronoi (cantos vivos), Voronoi (cantos arredondados), hexágonos (colmeia), malha triangular e círculos.
- **Relaxamento de Lloyd** deixa o tamanho das células mais uniforme (Voronoi e círculos).
- Permite usar **seus próprios pontos de semente** (pontos de esboço) e, se quiser, usar somente esses pontos.
- Tem **pré-visualização** opcional (desligada por padrão).
- Mostra um **relatório de análise medido** a cada execução (veja a seção 5).
- A janela, as mensagens e o relatório seguem o idioma do Fusion (inglês, português-BR ou espanhol).

### 2. Requisitos e Instalação
**Requisitos:** Autodesk Fusion 360 desktop (Windows ou macOS), espaço de trabalho Design. Sem bibliotecas externas.

**Opção A — pacote da release (recomendada):**
1. Baixe `VVGenerator-v1.7.0.zip` na página de **Releases** e descompacte.
2. Execute `install-windows.bat` (Windows) ou `install-macos.command` (macOS).

**Opção B — manual:** copie a pasta `VVGenerator` inteira (ela contém `VVGenerator.py`, `vv_engine.py`, `VVGenerator.manifest` e `resources/`) para o diretório de Add-Ins:
   - **Win:** `%appdata%\Autodesk\Autodesk Fusion 360\API\AddIns`
   - **Mac:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns`

Depois, no Fusion, vá em **Utilitários ▸ Add-Ins** (Shift+S), selecione **VV Generator** e clique em Executar. O botão aparece em **Sólido ▸ Criar**.

**Atualização:** substitua os arquivos e depois **pare** e **execute** o add-in novamente (reinicie o Fusion uma vez se o ícone da barra parecer antigo). Se ainda tiver a pasta antiga `VoronoiStructure`, apague-a para não ficar com dois botões.

### 3. Início Rápido
1. Acesse **Sólido ▸ Criar ▸ VV Generator**.
2. Selecione a **face plana**.
3. (Opcional) Selecione as **faces de reforço**. Mantenha a detecção automática de furos ligada.
4. (Opcional) Selecione **pontos de semente** de um esboço. Marque *Usar somente meus pontos* para gerar só essas células.
5. Escolha o **Formato** e ajuste os parâmetros (os valores padrão são uma boa primeira tentativa).
6. (Opcional) Marque **Pré-visualizar** para ver o resultado antes de confirmar. É mais lento, por isso vem desligado.
7. Clique em **OK**. Leia o relatório: ele mostra o que foi encontrado e o que foi removido.

### 4. Principais Opções
| Opção | Vale para | Descrição |
|---|---|---|
| Formato | Todos | Voronoi vivo / arredondado, hexágonos, triângulos, círculos |
| Raio dos cantos | Arredondado, hexágonos, triângulos | 0 = cantos vivos |
| Espessura da parede | Todos | Parede exata (Voronoi), folga mínima (círculos), parede mais fina (malhas) |
| Lado do ladrilho · Parede perto do reforço · Rotação da malha | Hexágonos, triângulos | Malha regular; a parede engrossa perto do reforço |
| Célula mínima / máxima · Distância de transição | Voronoi, círculos | Tamanho da célula perto / longe do reforço |
| Relaxamento | Voronoi, círculos | Passos de suavização de Lloyd (padrão 3, 0 = desligado) |
| Pontos de semente · Usar somente meus pontos | Voronoi, círculos | Centros de célula escolhidos por você |
| Zona sólida ao redor dos furos · Borda sólida | Todos | Material mantido ao redor dos furos e ao longo do contorno |
| Limite de células · Semente aleatória | Todos | Número máximo de células · variação do layout |
| Profundidade | Todos | Atravessar tudo, ou uma distância fixa |

### 5. Relatório de Análise
A cada execução, o add-in mostra (e grava no log do Fusion): área da face, caixa envolvente e comprimento do contorno; reforços encontrados; número e tamanho das formas; formas na zona reforçada e na zona leve; variação do tamanho das células; parede mínima medida; área aberta; cobertura e maior lacuna; volume e massa removidos; e avisos.
A análise é **geométrica** (proximidade de furos e reforços). Ela **não** é uma análise por elementos finitos — valide sempre com um estudo de simulação.

### 6. Limitações
- Somente faces planas. O resultado não é paramétrico: se a peça mudar, apague o esboço e o corte e execute o comando de novo.
- Análise geométrica, não MEF.
- Pescoços estreitos e cantos internos vivos podem ficar sólidos; o relatório avisa.
- Com *Usar somente meus pontos*, as regiões distantes dos seus pontos ficam sólidas (uma célula é sempre convexa).
- O motor geométrico e a camada do Fusion têm testes automatizados que rodam **fora** do Fusion. Eles não substituem a validação dentro do Fusion: teste em uma cópia da sua peça.

### 7. Histórico de Atualizações
| Versão | Alterações |
|---|---|
| **1.7.0** | Geração 2,3×–3,4× mais rápida; **relaxamento de Lloyd**; **seus próprios pontos de semente** (e "usar somente meus pontos"); **pré-visualização** opcional; melhor preenchimento de lacunas perto de contornos côncavos; o relatório mostra variação de tamanho das células, pontos de semente usados e tempo de geração. |
| **1.6.0** | Revisão completa do código. Novo motor geométrico (`vv_engine.py`) que garante que o padrão nunca cruze a borda sólida, mesmo em faces côncavas ou imprecisas; preenchimento automático de lacunas; **relatório de análise**; janela e mensagens seguem o idioma do Fusion; validação de entradas em tempo real; novos ícones da barra; tratamento mais seguro de componentes, falhas e limpeza; testes automatizados. |
| **1.5.0** | Malhas hexagonal (colmeia) e triangular de verdade, cobrindo toda a face, com parede que engrossa perto do reforço; lado do ladrilho e rotação da malha. |
| **1.4.0** | Seletor de formato: Voronoi arredondado, hexágonos, triângulos, círculos; raio dos cantos. |
| **1.3.0** | Renomeado para **VV Generator**; logo e rodapé na janela; diagnóstico e corte em lotes; filtro de células minúsculas. |
| **1.2.0** | Corte robusto: testa as duas direções e confere se o volume realmente diminuiu. |
| **1.1.0** | Células retas junto ao contorno com borda uniforme; zonas protegidas ao redor dos reforços; passadas extras de sementes para preencher vazios. |
| **1.0.0** | Primeira versão: Voronoi adaptativo em face plana, detecção de furos, esboço e corte. |

### 8. Créditos e Suporte
**Desenvolvido pela Equipe Flashbio #31888**
- **Cauã Vioto** — Criador Principal / Desenvolvedor Líder
- **Gabriel Chidi** — Apoio / Contribuidor
- **João Lacerda** — Apoio / Contribuidor

Ao relatar um problema, inclua a versão do Fusion, uma captura de tela, os valores dos parâmetros e o texto completo da mensagem exibida pelo add-in.
</details>

<details>
<summary><h2>🇪🇸 Parte III — Español</h2></summary>

### 1. Descripción General
VV Generator es un complemento en Python para Autodesk Fusion 360 que genera patrones de corte aligerados en una cara plana de un cuerpo sólido. Dibuja el patrón en un nuevo boceto y, en el mismo comando, lo corta a través del cuerpo con una operación Extrude (Cut).

**Qué hace:**
- Lee la cara seleccionada y los agujeros para decidir dónde se necesita estructura.
- Hace el patrón adaptativo: más material cerca de agujeros y caras de refuerzo, áreas más ligeras lejos.
- Mantiene un borde sólido a lo largo del contorno y una zona sólida alrededor de los agujeros — también en caras cóncavas, irregulares o imprecisas.
- Ofrece cinco formatos: Voronoi (esquinas vivas), Voronoi (esquinas redondeadas), hexágonos (panal), malla triangular y círculos.
- La **relajación de Lloyd** uniformiza el tamaño de las celdas (Voronoi y círculos).
- Permite usar **sus propios puntos semilla** (puntos de boceto) y, si lo desea, usar solo esos puntos.
- Tiene **vista previa** opcional (desactivada por defecto).
- Muestra un **informe de análisis medido** en cada ejecución (vea la sección 5).
- La ventana, los mensajes y el informe siguen el idioma de Fusion (inglés, portugués-BR o español).

### 2. Requisitos e Instalación
**Requisitos:** Autodesk Fusion 360 de escritorio (Windows o macOS), espacio de trabajo Design. Sin bibliotecas externas.

**Opción A — paquete de la release (recomendada):**
1. Descargue `VVGenerator-v1.7.0.zip` desde la página de **Releases** y descomprímalo.
2. Ejecute `install-windows.bat` (Windows) o `install-macos.command` (macOS).

**Opción B — manual:** copie la carpeta `VVGenerator` completa (contiene `VVGenerator.py`, `vv_engine.py`, `VVGenerator.manifest` y `resources/`) al directorio de Add-Ins:
   - **Win:** `%appdata%\Autodesk\Autodesk Fusion 360\API\AddIns`
   - **Mac:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns`

Luego, en Fusion, abra **Utilidades ▸ Add-Ins** (Shift+S), seleccione **VV Generator** y ejecútelo. El botón aparece en **Sólido ▸ Crear**.

**Actualización:** reemplace los archivos y luego **detenga** y **ejecute** el add-in de nuevo (reinicie Fusion una vez si el icono de la barra parece antiguo). Si aún tiene la carpeta antigua `VoronoiStructure`, elimínela para no tener dos botones.

### 3. Inicio Rápido
1. Vaya a **Sólido ▸ Crear ▸ VV Generator**.
2. Seleccione la **cara plana**.
3. (Opcional) Seleccione las **caras de refuerzo**. Mantenga activada la detección automática de agujeros.
4. (Opcional) Seleccione **puntos semilla** de un boceto. Marque *Usar solo mis puntos* para generar solo esas celdas.
5. Elija el **formato** y ajuste los parámetros (los valores predeterminados son un buen primer intento).
6. (Opcional) Marque **Vista previa** para ver el resultado antes de confirmar. Es más lenta, por eso viene desactivada.
7. Haga clic en **OK**. Lea el informe: muestra lo que se encontró y lo que se retiró.

### 4. Opciones Principales
| Opción | Se aplica a | Descripción |
|---|---|---|
| Formato | Todos | Voronoi vivo / redondeado, hexágonos, triángulos, círculos |
| Radio de esquinas | Redondeado, hexágonos, triángulos | 0 = esquinas vivas |
| Espesor de pared | Todos | Pared exacta (Voronoi), holgura mínima (círculos), pared más fina (mallas) |
| Lado de la baldosa · Pared cerca del refuerzo · Rotación de la malla | Hexágonos, triángulos | Malla regular; la pared se engrosa cerca del refuerzo |
| Celda mínima / máxima · Distancia de transición | Voronoi, círculos | Tamaño de celda cerca / lejos del refuerzo |
| Relajación | Voronoi, círculos | Pasos de suavizado de Lloyd (3 por defecto, 0 = desactivada) |
| Puntos semilla · Usar solo mis puntos | Voronoi, círculos | Centros de celda elegidos por usted |
| Zona sólida alrededor de agujeros · Borde sólido | Todos | Material que se mantiene alrededor de los agujeros y a lo largo del contorno |
| Límite de celdas · Semilla aleatoria | Todos | Número máximo de celdas · variación de la distribución |
| Profundidad | Todos | Atravesar todo, o una distancia fija |

### 5. Informe de Análisis
En cada ejecución, el add-in muestra (y escribe en el registro de Fusion): área de la cara, caja envolvente y longitud del contorno; refuerzos encontrados; número y tamaño de las formas; formas en la zona reforzada y en la zona ligera; variación del tamaño de las celdas; pared mínima medida; área abierta; cobertura y mayor hueco; volumen y masa retirados; y avisos.
El análisis es **geométrico** (cercanía a agujeros y refuerzos). **No** es un análisis por elementos finitos — valide siempre con un estudio de simulación.

### 6. Limitaciones
- Solo caras planas. El resultado no es paramétrico: si la pieza cambia, elimine el boceto y el corte y ejecute el comando de nuevo.
- Análisis geométrico, no FEM.
- Cuellos estrechos y esquinas internas vivas pueden quedar sólidos; el informe lo avisa.
- Con *Usar solo mis puntos*, las regiones lejanas a sus puntos quedan sólidas (una celda siempre es convexa).
- El motor geométrico y la capa de Fusion tienen pruebas automatizadas que se ejecutan **fuera** de Fusion. No sustituyen la validación dentro de Fusion: pruebe en una copia de su pieza.

### 7. Historial de Actualizaciones
| Versión | Cambios |
|---|---|
| **1.7.0** | Generación 2,3×–3,4× más rápida; **relajación de Lloyd**; **sus propios puntos semilla** (y "usar solo mis puntos"); **vista previa** opcional; mejor relleno de huecos cerca de contornos cóncavos; el informe muestra la variación de tamaño de celdas, los puntos semilla usados y el tiempo de generación. |
| **1.6.0** | Revisión completa del código. Nuevo motor geométrico (`vv_engine.py`) que garantiza que el patrón nunca cruce el borde sólido, incluso en caras cóncavas o imprecisas; relleno automático de huecos; **informe de análisis**; ventana y mensajes siguen el idioma de Fusion; validación de entradas en vivo; nuevos iconos de la barra; manejo más seguro de componentes, fallos y limpieza; pruebas automatizadas. |
| **1.5.0** | Mallas hexagonal (panal) y triangular verdaderas, que cubren toda la cara, con pared que se engrosa cerca del refuerzo; lado de la baldosa y rotación de la malla. |
| **1.4.0** | Selector de formato: Voronoi redondeado, hexágonos, triángulos, círculos; radio de esquinas. |
| **1.3.0** | Renombrado a **VV Generator**; logo y pie en la ventana; diagnóstico y corte por lotes; filtro de celdas diminutas. |
| **1.2.0** | Corte robusto: prueba ambas direcciones y verifica que el volumen realmente disminuyó. |
| **1.1.0** | Celdas rectas junto al contorno con borde uniforme; zonas protegidas alrededor de los refuerzos; pasadas extra de semillas para rellenar huecos. |
| **1.0.0** | Primera versión: Voronoi adaptativo en cara plana, detección de agujeros, boceto y corte. |

### 8. Créditos y Soporte
**Desarrollado por el Equipo Flashbio #31888**
- **Cauã Vioto** — Creador Principal / Desarrollador Líder
- **Gabriel Chidi** — Apoyo / Colaborador
- **João Lacerda** — Apoyo / Colaborador

Al reportar un problema, incluya la versión de Fusion, una captura de pantalla, los valores de los parámetros y el texto completo del mensaje mostrado por el add-in.
</details>

---

<p align="center">
  <i>Construído pela equipe <b>Flashbio #31888</b></i><br><br>
  <img src="assets/images/LOGO FLASHBIO.png" width="80" alt="FlashBio Logo Minimal"><br><br>
  <a href="https://www.instagram.com/flashbioftc/" target="_blank"><img src="https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white" alt="Instagram"></a>
  <a href="https://www.youtube.com/@FlashBio31888" target="_blank"><img src="https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="YouTube"></a>
  <a href="https://www.facebook.com/SesiRobobio/?locale=pt_BR" target="_blank"><img src="https://img.shields.io/badge/Facebook-1877F2?style=for-the-badge&logo=facebook&logoColor=white" alt="Facebook"></a>
</p>
