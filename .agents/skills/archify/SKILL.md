---
name: archify
description: Create polished, validated architecture, workflow, sequence, data-flow, and lifecycle/state diagrams as explorable standalone HTML with inline SVG, dark/light themes, optional trace motion, and PNG/JPEG/WebP/SVG/WebM export. Accept plain-language requirements or inspect repository evidence when the diagram must reflect real code. Use when visualizing system architecture, infrastructure, cloud/security/network topology, technical workflows, API call sequences, request lifecycles, data pipelines, ETL/ELT, data lineage, or state machines.
license: MIT
metadata:
  version: "2.17"
  author: tt-a1i
  repository: https://github.com/tt-a1i/archify
---

# Archify Agent Skill

Skill oficial para generar mapas y diagramas interactivos de arquitectura técnica a partir del código fuente.

## Tipos de Diagramas Soportados

1. **architecture**: Componentes, servicios, módulos, capas de seguridad Clean Architecture, conexiones a bases de datos y APIs externas.
2. **workflow**: Flujos de tareas, pipelines secuenciales, puertas de aprobación y runbooks.
3. **sequence**: Diagramas de secuencia temporal, llamadas asíncronas entre actores y cadenas de invocación de APIs.
4. **dataflow**: Flujos de datos, tuberías ETL/ELT, transformaciones e inspección perimetral.
5. **lifecycle**: Máquinas de estados finitos (FSM), transiciones de ciclo de vida de peticiones, tokens y manejo de errores.

## Formato de Salida

- Especificación JSON IR estructurada con metadatos tipados.
- Compilación a archivos `.html` autónomos con SVG vectorial en línea.
- Conmutador de temas (Dark Obsidian / Light Academic Paper).
- Resaltado interactivo de rutas de dependencias (upstream / downstream reach).
- Animaciones de pulsos de paquetes de datos y cajón de inspección técnica de código fuente.
