This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Telemetria: servicio de captura

Configurar `NEXT_PUBLIC_TELEMETRY_ENDPOINT` en `.env.local` con una URL accesible
desde el navegador, por ejemplo `http://localhost:8000/telemetry/events` para
desarrollo local. En Codespaces/despliegues, usar la URL accesible del backend.
La variable es publica: no incluir secretos. Reiniciar Next.js tras cambiarla;
en produccion se incorpora al build. Sin endpoint, la captura queda desactivada.

`track()` en `app/telemetry.ts` es la unica entrada de captura. Actualmente admite
los eventos frontend `section_viewed`, `workflow_started`, `workflow_cancelled`
y `frontend_error_detected`, seleccionando propiedades permitidas. Registra
transiciones a secciones despues de validar acceso, el primer cambio y la
cancelacion explicita de formularios de entrada/salida de inventario, creacion
de proveedor, tarifa, incidencia y perfil. Abrir un formulario no es iniciarlo;
salir de una pagina no se declara como cancelacion ni abandono.
No genera resultados de negocio ni obtiene identidad de tokens sin verificar.
El exito funcional solo cierra el flujo local; no emite `workflow_completed`.
Los errores globales y fallos de conexion de inventario usan codigos controlados,
sin mensajes libres, y se limitan por firma/seccion/version durante 60 segundos.

El servicio mantiene hasta 200 eventos en memoria, envia lotes de hasta 20 cada
5 segundos o al alcanzar el limite, y limita cada cuerpo a 64 KiB. En saturacion
prioriza retirar visitas de la cola; si no hay ninguna, descarta la nueva captura.
No almacena eventos en el navegador: solo conserva un UUID pseudonimo por pestana
en `sessionStorage`, con fallback en memoria si esta restringido. Diagnosticos agregados de cola
y descarte estan disponibles mediante `getDiagnostics()`, sin exponer payloads.

Reintenta fallos de red, timeout de 10 segundos, HTTP 429 y 5xx: hasta cinco
intentos totales por lote, con backoff exponencial y jitter, respetando
`Retry-After`. Otros errores HTTP descartan el lote. IDs y timestamps permanecen
iguales al reintentar. La telemetria nunca espera una respuesta para permitir
una operacion de la interfaz.

El proveedor del layout inicia y detiene el servicio. Al ocultar o abandonar la
pagina intenta `sendBeacon`; los envios normales usan `keepalive`. Un beacon
aceptado por el navegador no confirma recepcion del servidor. Ambos mecanismos
comparten limites del navegador y no garantizan entrega. El stub actual no exige
autenticacion ni acredita la identidad declarada: esto no sustituye los controles
de ingesta de una implementacion de produccion.

Los seis eventos obligatorios de inventario siguen pendientes: el contrato exige
hechos confirmados en backend y datos/reglas que aun faltan (proveedor estable,
precios reales, causas de merma, catalogo de locales, stock/minimo por local y
rechazo explicito de edicion directa). No se emiten payloads inventados ni se
considera completada su instrumentacion por tener el receptor y la captura UI.

Pruebas del servicio, desde la raiz del monorepo con las dependencias raiz instaladas:

```bash
npm test -- --runInBand --roots '<rootDir>/uis/backoffice/app' --testMatch '**/telemetry.test.ts'
```

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
