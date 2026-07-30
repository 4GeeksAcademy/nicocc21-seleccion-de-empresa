# Skill: scaffold-next-app

---

## Objetivo

Crear una nueva aplicación Next.js + TypeScript dentro del directorio `uis/` del monorepo Brasaland, siguiendo la estructura establecida y sin romper funcionalidad existente.

---

## Inputs

| Input | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `nombreApp` | string | Sí | Nombre de la app (ej: `website`, `backoffice`). Se usará como carpeta dentro de `uis/`. |
| `descripcion` | string | Sí | Descripción breve del propósito de la app. |
| `esPublica` | boolean | Sí | `true` si es para clientes externos, `false` si es uso interno. |
| `requiereAuth` | boolean | No | Si la app necesita autenticación (default: `false`). |

---

## Proceso

### Paso 1: Verificar que no existe
```bash
ls uis/<nombreApp>
```
Si la carpeta ya existe, **detenerse** y reportar que la app ya fue creada.

### Paso 2: Crear estructura de carpetas
```
uis/<nombreApp>/
├── app/
│   ├── layout.tsx          # Layout raíz de la app
│   ├── page.tsx            # Página principal (ruta /)
│   └── globals.css         # Estilos globales
├── public/                 # Assets estáticos
├── package.json            # Dependencias de la app
├── tsconfig.json           # Configuración TypeScript
├── next.config.ts          # Configuración de Next.js
├── postcss.config.mjs      # Configuración de PostCSS
├── eslint.config.mjs       # Configuración de ESLint
└── README.md               # Documentación de la app
```

### Paso 3: Configurar `package.json`
- Nombre: `brasaland-<nombreApp>`
- Scripts mínimos: `dev`, `build`, `start`, `lint`
- Dependencias: `next`, `react`, `react-dom`
- DevDependencies: `typescript`, `@types/react`, `@types/react-dom`, `@types/node`

### Paso 4: Configurar `tsconfig.json`
- `strict: true`
- `paths` configurados si es necesario para imports relativos
- Compatible con la configuración raíz del monorepo

### Paso 5: Crear layout base
- Layout con `<html lang="es">` 
- Metadata básica (título, descripción)
- Importación de `globals.css`

### Paso 6: Crear página principal
- Ruta `/` funcional
- Contenido mínimo visible (título de la app)
- Componente React con TypeScript correcto

### Paso 7: Verificar
- Ejecutar `npm install` dentro de la carpeta de la app
- Ejecutar `npm run dev` y verificar que arranca sin errores
- Verificar que la ruta `/` renderiza contenido

---

## Criterios de Aceptación

| # | Criterio | Verificación |
|---|----------|--------------|
| 1 | La carpeta `uis/<nombreApp>/` existe con la estructura correcta | `ls uis/<nombreApp>/app/` muestra `layout.tsx` y `page.tsx` |
| 2 | `package.json` tiene los scripts `dev`, `build`, `start` | `cat uis/<nombreApp>/package.json \| grep '"dev"'` |
| 3 | `tsconfig.json` tiene `strict: true` | `cat uis/<nombreApp>/tsconfig.json \| grep strict` |
| 4 | `npm run dev` arranca sin errores | El servidor inicia y muestra "Ready" en consola |
| 5 | La ruta `/` renderiza contenido visible | Abrir `http://localhost:3000` y ver el título de la app |
| 6 | No se modificó ningún archivo fuera de `uis/<nombreApp>/` | `git status` no muestra cambios en otras carpetas |
| 7 | El `README.md` describe la app y cómo ejecutarla | El archivo existe y contiene instrucciones de uso |

---

## Ejemplo de uso

```
Scaffold: uis/website
Descripción: Web pública corporativa de Brasaland
Es pública: true
Requiere auth: false
```

Resultado: App Next.js en `uis/website/` con layout, página principal, y configuración lista para desarrollo.
