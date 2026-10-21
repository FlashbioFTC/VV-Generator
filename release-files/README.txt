VV Generator for Autodesk Fusion 360  -  v1.7.0
Created and maintained by Flashbio #31888

EN  Adaptive lightweight patterns (Voronoi, rounded Voronoi, honeycomb hexagons, triangular mesh, circles) cut into a planar face,
    with Lloyd relaxation (more even cells), optional seed points chosen by you, live preview and a measured analysis report (areas, walls, coverage, volume and mass removed). The dialog follows Fusion's language (EN / PT-BR / ES).
    Install: run install-windows.bat (Windows) or install-macos.command (macOS), or copy the "VVGenerator" folder to:
      Windows: %APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns
      macOS:   ~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns
    Then in Fusion: Utilities > Add-Ins (Shift+S) > VV Generator > Run. Button: Solid > Create.
    Updating: Stop and Run the add-in again (restart Fusion once if the icon looks stale). Delete the old "VoronoiStructure" folder if you have it.

PT  Padroes leves adaptativos (Voronoi, Voronoi arredondado, favo de mel, malha triangular, circulos) cortados numa face plana,
    com relaxamento de Lloyd (celulas mais uniformes), pontos de semente escolhidos por voce, pre-visualizacao e relatorio de analise medido (areas, paredes, cobertura, volume e massa removidos). A janela segue o idioma do Fusion (EN / PT-BR / ES).
    Instalacao: execute install-windows.bat (Windows) ou install-macos.command (macOS), ou copie a pasta "VVGenerator" para a pasta de add-ins (caminhos acima).
    No Fusion: Utilities > Add-Ins (Shift+S) > VV Generator > Run.
    Atualizacao: pare e execute o add-in de novo (reinicie o Fusion uma vez se o icone parecer antigo). Apague a pasta antiga "VoronoiStructure", se existir.

ES  Patrones ligeros adaptativos (Voronoi, Voronoi redondeado, panal, malla triangular, circulos) cortados en una cara plana,
    con relajacion de Lloyd (celdas mas uniformes), puntos semilla elegidos por usted, vista previa e informe de analisis medido (areas, paredes, cobertura, volumen y masa retirados). La ventana sigue el idioma de Fusion (EN / PT-BR / ES).
    Instalacion: ejecute install-windows.bat (Windows) o install-macos.command (macOS), o copie la carpeta "VVGenerator" al directorio de add-ins (rutas arriba).
    En Fusion: Utilities > Add-Ins (Shift+S) > VV Generator > Run.
    Actualizacion: detenga y ejecute el add-in de nuevo (reinicie Fusion una vez si el icono parece antiguo). Elimine la carpeta antigua "VoronoiStructure", si existe.

Note: the analysis is geometric, not FEA. Validate structural performance with a simulation study.
