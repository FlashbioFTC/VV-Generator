<p align="center">
  <img src="assets/images/LOGO FLASHBIO.png" width="250" alt="FlashBio Logo">
</p>

<h1 align="center">VV Generator</h1>

<p align="center">
  <em>Adaptive lightweight patterns for Autodesk Fusion 360</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.5.0--beta-orange.svg?style=flat-square" alt="Version">
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
- Keeps a solid rim along the outline of the face and a solid zone around holes.
- Offers five formats: Voronoi (sharp corners), Voronoi (rounded corners), honeycomb hexagons, triangular mesh and circles.

### 2. Requirements and Installation
**Requirements:** Autodesk Fusion 360 desktop (Windows or macOS), Design workspace. No external libraries needed.

**Installation:**
1. Copy the `VVGenerator` folder to the Add-Ins directory:
   - **Win:** `%appdata%\Autodesk\Autodesk Fusion 360\API\AddIns`
   - **Mac:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns`
2. In Fusion, open **Utilities ▸ Add-Ins** (Shift+S), select **VV Generator** and run it.

### 3. Quick Start
1. Go to **Solid ▸ Create ▸ VV Generator**.
2. Select the **planar face**.
3. (Optional) Select **reinforcement faces**. Keep *Detect holes automatically* on.
4. Choose the **Shape** and parameters.
5. Click **OK**.

### 4. Credits and Support
**Developed by Team Flashbio #31888**
- **Cauã Vioto** — Lead Creator / Principal Developer
- **Gabriel Chidi** — Support / Contributor
- **João Lacerda** — Support / Contributor

When reporting an issue, include the Fusion version, a screenshot, parameter values, and the full text of the error message.
</details>

<details>
<summary><h2>🇧🇷 Parte II — Português (Brasil)</h2></summary>

### 1. Visão Geral
O VV Generator é um add-in em Python para o Autodesk Fusion 360 que gera padrões de corte leves em uma face plana de um corpo sólido. Ele desenha o padrão em um novo esboço e, no mesmo comando, o corta através do corpo com uma extrusão (Corte).

**O que ele faz:**
- Lê a face selecionada e os furos do corpo para decidir onde é necessária estrutura.
- Torna o padrão adaptativo: mais material ao redor de furos e faces de reforço, áreas mais leves e abertas mais longe.
- Mantém uma borda sólida ao longo do contorno e uma zona sólida ao redor dos furos.
- Oferece cinco formatos: Voronoi (cantos vivos), Voronoi (cantos arredondados), hexágonos (colmeia), malha triangular e círculos.

### 2. Requisitos e Instalação
**Requisitos:** Autodesk Fusion 360 desktop (Windows ou macOS), espaço de trabalho Design. Sem bibliotecas externas.

**Instalação:**
1. Copie a pasta `VVGenerator` para o diretório de Add-Ins:
   - **Win:** `%appdata%\Autodesk\Autodesk Fusion 360\API\AddIns`
   - **Mac:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns`
2. No Fusion, vá em **Utilitários ▸ Add-Ins** (Shift+S), selecione **VV Generator** e clique em Executar.

### 3. Início Rápido
1. Acesse **Sólido ▸ Criar ▸ VV Generator**.
2. Selecione a **face plana**.
3. (Opcional) Selecione as **faces de reforço**. Mantenha a detecção automática de furos ligada.
4. Escolha o **Formato** (Shape) e ajuste os parâmetros.
5. Clique em **OK**.

### 4. Créditos e Suporte
**Desenvolvido pela Equipe Flashbio #31888**
- **Cauã Vioto** — Criador Principal / Desenvolvedor Líder
- **Gabriel Chidi** — Apoio / Contribuidor
- **João Lacerda** — Apoio / Contribuidor

Ao relatar um problema, inclua a versão do Fusion, uma captura de tela, os valores dos parâmetros e o texto completo do erro exibido.
</details>

<details>
<summary><h2>🇪🇸 Parte III — Español</h2></summary>

### 1. Descripción General
VV Generator es un complemento en Python para Autodesk Fusion 360 que genera patrones de corte aligerados en una cara plana de un cuerpo sólido.

**Qué hace:**
- Lee la cara seleccionada y los agujeros para decidir dónde se necesita estructura.
- Hace el patrón adaptativo: más material cerca de agujeros y áreas de refuerzo, áreas más ligeras lejos.
- Mantiene un borde sólido a lo largo del contorno y alrededor de los agujeros.
- Ofrece cinco formatos: Voronoi (esquinas afiladas), Voronoi (esquinas redondeadas), hexágonos, triángulos y círculos.

### 2. Requisitos e Instalación
**Requisitos:** Autodesk Fusion 360 (Windows o macOS), espacio de trabajo Design. Sin bibliotecas externas.

**Instalación:**
1. Copie la carpeta `VVGenerator` al directorio de Add-Ins:
   - **Win:** `%appdata%\Autodesk\Autodesk Fusion 360\API\AddIns`
   - **Mac:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns`
2. En Fusion, abra **Utilidades ▸ Add-Ins** (Shift+S), seleccione **VV Generator** y ejecútelo.

### 3. Inicio Rápido
1. Vaya a **Sólido ▸ Crear ▸ VV Generator**.
2. Seleccione la **cara plana**.
3. Seleccione las caras de refuerzo (opcional).
4. Elija el formato y ajuste los parámetros.
5. Haga clic en **OK**.

### 4. Créditos y Soporte
**Desarrollado por el Equipo Flashbio #31888**
- **Cauã Vioto** — Creador Principal / Desarrollador Líder
- **Gabriel Chidi** — Apoyo / Colaborador
- **João Lacerda** — Apoyo / Colaborador

Al reportar un problema, incluya la versión de Fusion, una captura de pantalla, los valores de los parámetros y el texto completo del error.
</details>

---

<p align="center">
  <i>Construído pela equipe <b>Flashbio #31888</b></i><br><br>
  <img src="assets/images/LOGO FLASHBIO.png" width="80" alt="FlashBio Logo Minimal"><br><br>
  <a href="https://www.instagram.com/flashbioftc/" target="_blank"><img src="https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white" alt="Instagram"></a>
  <a href="https://www.youtube.com/@FlashBio31888" target="_blank"><img src="https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="YouTube"></a>
  <a href="https://www.facebook.com/SesiRobobio/?locale=pt_BR" target="_blank"><img src="https://img.shields.io/badge/Facebook-1877F2?style=for-the-badge&logo=facebook&logoColor=white" alt="Facebook"></a>
</p>
