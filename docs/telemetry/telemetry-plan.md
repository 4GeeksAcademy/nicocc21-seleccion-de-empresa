# Plan de telemetría de Brasaland

## 1. Objetivo, alcance y entregables

Responder al RFI del equipo de gestión: identificar datos accionables del inventario y del backoffice de Brasaland, cadena de 14 locales en Colombia y Florida. El diseño debe servir para operaciones de Felipe, compras de Lucía, trazabilidad de Jake y reportes ejecutivos de Mariana, sin convertir esta entrega en un dashboard o una implementación de captura.

Los entregables son este plan y [event-schemas.json](event-schemas.json). El catálogo contiene **22 eventos: 6 obligatorios y 16 oportunidades identificadas**, en negocio/inventario, autenticación y permisos, navegación/flujos, rendimiento, errores y procesos internos. P0 significa obligatorio; P1, primera instrumentación recomendada; P2, ampliación posterior. Prioridad no sustituye clasificación de origen.

El catálogo y contrato fueron aprobados por pasos. Esta fase crea documentación de diseño; no instrumenta la aplicación, instala dependencias, cambia modelos o levanta servidores. Los parámetros operativos señalados como propuestas requieren aprobación antes de implementarse. No se afirma que se haya verificado el despliegue en producción.

Referencias: [contexto de Brasaland](../../CONTEXT.md), [arquitectura actual](../../memory-bank/techContext.md), [rutas de inventario](../../services/brasaland_api/routes/inventory.py), [esquemas existentes](../../services/brasaland_api/schemas.py) y [modelos SQL](../../services/brasaland_api/inventory_models.py).

## 2. Flujo y puntos de instrumentación

Flujo principal: usuario autenticado -> backoffice -> consulta de inventario -> formulario -> validación -> proxy Next.js -> FastAPI -> autorización y reglas de negocio -> transacción SQL -> respuesta -> actualización de UI. El frontend registra intención e interacción; el backend es fuente de verdad de resultados persistidos. No contar el éxito también en frontend y proxy.

| Punto | Eventos candidatos | Evidencia y límite |
| --- | --- | --- |
| 1. Acceso al sistema | login_succeeded, login_failed, authorization_denied | Login acepta/rechaza credenciales en backend; permisos se observan en el control que realmente deniega |
| 2. Visita de sección | section_viewed | Navegación confirmada del backoffice, no renderizado repetido |
| 3. Inicio/cancelación de formulario | workflow_started, workflow_cancelled | Primer cambio o cancelación explícita; no cada pulsación |
| 4. Validación de solicitud | validation_failed | Errores de campos saneados; no conservar valores ni body |
| 5. Edición directa de stock | direct_stock_edit_rejected | Punto requerido pero aún sin rechazo explícito identificable; ausencia de ruta o campos ignorados no prueba el evento |
| 6. Entrada confirmada | inbound_order_created, workflow_completed | Emitir solo para una orden persistida |
| 7. Salida confirmada o rechazada | outbound_order_created, stock_waste_registered, inventory_order_rejected | Separar consumo, merma y denegación por stock insuficiente |
| 8. Revisión de stock tras salida | stock_threshold_triggered | Necesita stock antes/después y mínimo por producto/local |
| 9. Revisión de precio de entrada | ingredient_price_variance_detected | Necesita costo real, proveedor estable e histórico comparable |
| 10. Respuesta y errores técnicos | api_request_completed, frontend_error_detected | Distinguir duración del proxy y del backend; no sumar ambas como nuevas peticiones |

El cliente de inventario está en [lib.ts](../../uis/backoffice/app/inventory/lib.ts); el proxy está en [route.ts](../../uis/backoffice/app/api/inventory/%5B...path%5D/route.ts). El stock SQL se deriva de entradas menos salidas; no se agrega una columna editable.

## 3. Dependencias y correspondencia con el contexto

| Requisito de Brasaland | Situación actual / decisión |
| --- | --- |
| Product / InboundOrder / OutboundOrder | Correspondencia conceptual con Ingredient / IngredientEntry / IngredientExit; no renombrar modelos |
| location: L01-L14 y país del local | Movimientos SQL usan enteros 1-14; verificar identidad y catálogo autoritativo antes de convertir n a L seguido de dos dígitos |
| Country / moneda / zona horaria | Obtenerlos del local validado, nunca del idioma UI o del país del ingrediente; el catálogo de locales no se verificó en esta fase |
| supplier | Entrada guarda supplier_name; falta ID estable, sin inferir identidad solo por el nombre |
| Precios y montos | Entrada no registra costo unitario ni moneda; requiere ampliación autorizada y datos reales de compras |
| Motivos de merma | Esquema actual solo distingue consumption/waste; capturar explícitamente expired/kitchen_error/theft_suspected |
| Stock y mínimo por local | Cálculo actual y mínimo son por ingrediente; falta cálculo/configuración por producto/local |
| Rechazo de edición directa | Definir operaciones prohibidas y rechazo observable; los esquemas revisados no rechazan explícitamente todos los campos extra |
| Correlación | Proxy reenvía Authorization, no requestId; falta propagación de correlación |
| Tarifas de proveedores | Modelo registra rate_per_unit y currency, pero no una unidad inequívoca para cada tarifa; no emitir el evento de tarifa hasta resolverla |

Los eventos que requieren datos ausentes quedan bloqueados, no se emiten incompletos ni con valores inventados. Esta tabla no autoriza cambios de código. TinyDB se usa en otros módulos de la API; la futura outbox SQL del inventario no garantiza atomicidad de esos módulos.

Categorías canónicas: meat (proteína), produce (vegetal), sauce (salsa), beverage (bebida), packaging (empaque), cleaning (limpieza). No confundirlas con las categorías del modelo TypeScript histórico o con las categorías de proveedores. Unidades canónicas: kg, unit, liter; equivalencias de etiqueta: und -> unit, L -> liter. No convertir cantidades ni dimensiones; una unidad desconocida requiere correspondencia aprobada.

## 4. Event Envelope y contrato

| Campo obligatorio | Tipo / significado |
| --- | --- |
| eventId | UUID único, conservado en reintentos |
| timestamp | ISO 8601 UTC terminado en Z, instante del hecho registrado, no del reenvío |
| sessionId | UUID pseudónimo o null si no existe sesión; no token de autenticación |
| userId | ID interno opaco o null si no hay usuario identificado; nunca nombre/email |
| event_type | Nombre exacto del catálogo, taxonomía entidad_acción con verbos consistentes |
| schemaVersion | Versión exacta por tipo; inicialmente 1.0.0 |
| requestId | UUID de correlación de la operación |
| properties | Payload específico con allowlist cerrada |

Un productor genera requestId al iniciar la operación si no recibe uno válido; se propaga como X-Request-ID entre frontend, proxy, FastAPI y logs saneados. Cada evento tiene eventId distinto aunque comparta requestId. Procesos internos generan correlación por ejecución. El servidor verifica la identidad y decide el resultado; no acepta userId o éxito de negocio declarados por un cliente. sessionId nunca se usa como prueba de autorización.

Base de inventario obligatoria: location_id (L01-L14), country (CO/US), product_id (ID interno como cadena de entero positivo), product_category (categoría canónica), quantity (número finito positivo), unit (unidad canónica), currency (COP/USD). País y moneda se validan juntos: CO/COP y US/USD. Para umbral o variación de precio, quantity es la del movimiento causante, no stock ni diferencia monetaria.

Excepción explícita: direct_stock_edit_rejected mantiene todas las claves base pero admite null donde no se conoce un valor validado. Local/país/moneda son todos conocidos y coherentes o todos null. Sin producto, categoría/unidad son null. Una quantity no nula exige unidad conocida y cantidad de movimiento positiva; un stock objetivo no se copia como quantity. No guardar el payload arbitrario.

Dinero: cadenas decimales no negativas con dos decimales, sin separadores de miles; precios unitarios y referencias estrictamente positivos. Usar aritmética decimal, sin conversión COP/USD. Total de entrada = quantity por unit_price, redondeado HALF_UP a dos decimales. Este formato no recupera precisión ya perdida en el origen. Un costo que no puede representarse válidamente requiere diagnóstico, no redondeo silencioso a un precio cero.

Todos los campos específicos declarados son obligatorios en 1.0.0; null no significa que pueda omitirse una clave. El esquema documenta tipo, rango y descripción directamente o mediante $ref. Cada variante tiene descripción; required expresa obligatoriedad, additionalProperties:false o unevaluatedProperties:false expresa la allowlist. El envelope también es cerrado. JSON Schema Draft 2020-12 es la estructura validable elegida; deben habilitarse formatos y validación semántica adicional.

## 5. Catálogo: hipótesis, decisiones y entrega

Cada fila completa la regla: capturamos event_type porque necesitamos saber la hipótesis, lo que permite tomar la decisión indicada. Las propiedades listadas se suman al envelope; solo los seis obligatorios incluyen la base de inventario. Las descripciones y tipos de cada propiedad están en el esquema.

### 5.1. Obligatorios: seis eventos del contexto

| Evento / origen y disparador | Hipótesis -> decisión | Propiedades además de base | Prioridad / procesamiento y urgencia |
| --- | --- | --- | --- |
| inbound_order_created / backend, entrada confirmada | Conocer compras por local/proveedor -> consolidar compras y negociar precios | order_id, supplier_id, unit_price, total_amount | P0 / batch diario: negociación necesita consolidación, no reacción por segundo |
| outbound_order_created / backend, consumo confirmado | Conocer ritmo de consumo -> ajustar sugerencias de reposición | order_id, reason=consumption | P0 / batch diario: planificación del siguiente pedido |
| stock_waste_registered / backend, merma confirmada | Conocer pérdidas y causas -> priorizar auditorías | order_id, reason=expired/kitchen_error/theft_suspected | P0 / batch diario: comparar pérdidas acumuladas |
| stock_threshold_triggered / backend, cruce del mínimo | Detectar insuficiencia de producto/local -> reabastecer y revisar mínimos | stock_before, stock_after, minimum_stock, order_id | P0 / stream: no esperar al día siguiente ante riesgo operativo |
| direct_stock_edit_rejected / backend, intento explícito rechazado | Detectar intentos de eludir trazabilidad -> revisar permisos/capacitación | rejection_code, operation, attempted_fields; base nullable según sección 4 | P0 / batch diario: revisar recurrencia por local |
| ingredient_price_variance_detected / backend, precio supera umbral | Detectar cambios anómalos -> renegociar o buscar alternativas | order_id, supplier_id, unit_price, reference_price, variance_pct, threshold_pct | P0 / stream: revisar precio antes de siguientes compras |

### 5.2. Oportunidades identificadas: dieciséis eventos

| Evento / origen y disparador | Hipótesis -> decisión | Allowlist específica | Prioridad / procesamiento y urgencia |
| --- | --- | --- | --- |
| inventory_order_rejected / backend, orden denegada | Localizar bloqueos operativos -> mejorar reglas/formularios | order_type, rejection_code, location_id, product_id; IDs nullable | P1 / batch diario: revisar patrones recurrentes |
| validation_failed / backend, solicitud inválida | Localizar campos con errores -> corregir contratos/validación | route_template, field_names, validation_codes | P1 / batch diario: priorizar por frecuencia |
| login_succeeded / backend, credenciales aceptadas | Conocer acceso efectivo -> dimensionar soporte/uso | auth_method | P1 / batch diario: tendencia de acceso |
| login_failed / backend, credenciales rechazadas | Detectar fallos anómalos -> investigar/ajustar controles | failure_code, auth_method | P1 / stream agregado: detectar ráfagas mientras ocurren |
| authorization_denied / backend, permiso denegado | Detectar permisos inadecuados -> revisar roles | operation, required_role, denial_code | P1 / batch diario: ajustar permisos a patrones |
| section_viewed / frontend, navegación confirmada | Conocer secciones usadas -> priorizar mejoras | section_code | P1 / batch diario: comparar uso, no actuar por cada visita |
| workflow_started / frontend, primer cambio | Conocer intención -> medir conversión del flujo | workflow_id, workflow_type | P1 / batch diario: comparar inicios con resultados |
| workflow_completed / backend, operación persistida | Conocer finalizaciones reales -> localizar pérdidas | workflow_id, workflow_type, entity_id | P1 / batch diario: evaluar conversión |
| workflow_cancelled / frontend, cancelación explícita | Conocer cancelaciones voluntarias -> simplificar el flujo | workflow_id, workflow_type, step_code | P1 / batch diario: mejorar pasos problemáticos |
| api_request_completed / backend o proxy, respuesta terminada | Detectar latencia/errores por ruta -> priorizar correcciones/capacidad | route_template, method, status_code, duration_ms, source | P1 / stream para degradación; batch diario para tendencias |
| frontend_error_detected / frontend, error no controlado | Detectar fallos visibles -> priorizar arreglos | error_code, section_code, release_version | P1 / stream agregado: contener regresiones de una versión |
| supplier_rate_updated / backend, tarifa confirmada | Seguir cambios de tarifa -> revisar compras | supplier_id, previous_rate, new_rate, currency, unit | P2 / batch diario: comparar evolución comercial |
| supplier_status_changed / backend, estado confirmado | Conocer disponibilidad -> revisar alternativas | supplier_id, previous_status, new_status | P2 / batch diario: revisión comercial periódica; alertas inmediatas requerirían otro SLA |
| incident_created / backend, incidencia confirmada | Conocer problemas por local/categoría -> asignar recursos | incident_id, location_id, category, priority | P2 / batch diario: carga operativa; no sustituye atención urgente de incidencias |
| incident_status_changed / backend, transición confirmada | Medir resolución/acumulación -> ajustar atención | incident_id, previous_status, new_status | P2 / batch diario: evaluar resolución y pendientes |
| background_job_completed / proceso, ejecución terminada si existe | Detectar fallos de automatización -> reintentar/corregir | job_type, run_id, outcome, duration_ms, error_code | P2 / stream para fallos; resumen diario de éxito |

Cada properties se diseña sin PII ni datos sensibles personales. El envelope sí contiene IDs pseudónimos de usuario/sesión cuando aplican y requiere acceso restringido. No confundir pseudonimización con anonimización irreversible. supplier_rate_updated y eventos de compras contienen información comercial sensible: limitar lectura a roles autorizados.

## 6. Semántica, códigos y consistencia

1. Emitir éxitos solo de órdenes confirmadas. Una salida consumption genera outbound; una merma genera waste, no también outbound. order_id es de la tabla de entrada para inbound/precio y de salida para outbound/merma/umbral; no es un ID global entre tablas.
2. Obtener usuario del contexto autenticado. El esquema exige userId no nulo en órdenes, merma, umbral, variación, login exitoso y workflow_completed; login_failed usa null y código genérico INVALID_CREDENTIALS, sin distinguir usuario inexistente de contraseña incorrecta. Sesión puede ser null en integraciones sin sesión.
3. Cruce: por producto/local, stock_before >= minimum_stock y stock_after < minimum_stock, con stock_after = stock_before - quantity. No emitir por lecturas ni por seguir bajo. La igualdad con el mínimo no dispara. Recuperarse y caer nuevamente genera otro evento.
4. Consistencia concurrente: stock antes/después debe corresponder a la transacción causante. La comprobación actual previa al commit no demuestra protección contra salidas concurrentes; resolver aislamiento/bloqueo por producto/local antes de instrumentar.
5. Referencia de precio: mediana de precios positivos de al menos tres entradas comparables anteriores en [timestamp - 30 días, timestamp), excluyendo la entrada evaluada; mismo producto, proveedor, país, moneda y unidad. Si la mediana requiere más de dos decimales, normalizar HALF_UP a dos antes de calcular la variación. Definir orden determinista para empates temporales sin incluir la orden actual.
6. variance_pct = 100 por (unit_price - reference_price) / reference_price. Emitir si abs(variance_pct) > threshold_pct; umbral inicial 10, configurable y registrado. Comparar sin redondear porcentajes para presentación. Sin histórico suficiente/referencia positiva no emitir una variación ficticia; medir cobertura con diagnósticos agregados.
7. workflow_id es UUID distinto de requestId, creado al inicio y propagado al backend. En 1.0.0, los flujos cubren operaciones autenticadas de inventario, proveedores, incidencias y perfil; no recuperación de contraseña. Abandono es inferencia tras 30 minutos sin finalización/cancelación; reconciliar finalizaciones tardías y excluir cancelaciones. Cerrar una pestaña no prueba abandono.
8. Estados reales: proveedores active/suspended; incidencias abierta/en_progreso/resuelta/descartada. La transición válida es abierta -> en_progreso o descartada; en_progreso -> resuelta o descartada. No confundir con abierto/cerrado/descartado del CSV histórico. No emitir cambios cuyo estado no cambie.
9. Tarifas de proveedores no son costo real de entradas. Datos de cliente, title, description, notes y contact_email quedan fuera de allowlists aunque existan en modelos fuente.
10. route_template es una ruta parametrizada registrada; usar /unmatched para rutas desconocidas, no URL/IDs/query strings. duration_ms se mide con reloj monotónico. success de un job implica error_code null; failure exige código controlado. Datos técnicos de error excluyen stacks y mensajes libres.

Registro propuesto para productores: section_code en dashboard/inventory_products/inventory_orders/suppliers/incidents/profile; workflow_type en inventory_inbound/inventory_outbound/supplier_create/supplier_rate_update/supplier_status_update/incident_create/incident_status_update/profile_update; step_code en form/review/submit. Nuevas etiquetas requieren revisión del contrato/registro, no texto dinámico.

Códigos propuestos de orden: INSUFFICIENT_STOCK, PRODUCT_NOT_FOUND, VALIDATION_ERROR, UNAUTHENTICATED, FORBIDDEN. Validación: REQUIRED, INVALID_TYPE, INVALID_VALUE, OUT_OF_RANGE, INVALID_JSON. Nombres de campo se toman del esquema conocido; errores de body desconocido usan body y códigos genéricos. Permisos: UNAUTHENTICATED o INSUFFICIENT_ROLE; required_role y operation provienen de la política existente, nunca del cliente. Frontend: UNHANDLED_ERROR, UNHANDLED_REJECTION o API_CONNECTION_FAILED; jobs: JOB_EXECUTION_FAILED. Son etiquetas de diseño, no códigos ya instrumentados. El esquema limita su forma; el registro y la semántica deben validarse adicionalmente.

## 7. Captura, entrega, duplicados y fallos

Arquitectura propuesta para implementación posterior: productores -> ingesta FastAPI validada -> PostgreSQL de telemetría -> procesamiento stream/batch -> agregados/reportes. No se introduce un broker nuevo ni un servidor en esta entrega.

Para movimientos SQL, proponer outbox en la misma transacción que la orden; asignar eventId una vez y publicar solo registros confirmados. El despachador entrega al menos una vez y conserva IDs/timestamps al reintentar. La transacción no realiza llamadas de red. Una reversión no publica éxito. Cambiar la base para esto necesita autorización futura. La outbox SQL no garantiza atomicidad de TinyDB ni entrega del navegador: esas brechas se documentan y monitorizan, no se promete ausencia de pérdidas.

La futura ingesta comprueba tamaño, origen, identidad, esquema, versión, formatos y semántica; confirma recepción después de almacenamiento durable. Frontend solo puede producir interacción/error UI, no resultados de negocio, permisos o login. source/event_type/userId declarados por el cliente no otorgan confianza. Transporte HTTPS y controles de origen/autenticación adecuados; nunca tokens dentro de properties. Evitar recursión excluyendo la propia ingesta de api_request_completed.

Parámetros operativos propuestos: lotes frontend de hasta 20 eventos, envío cada 5 segundos, cuerpo hasta 64 KiB y cola en memoria de hasta 200 eventos. Si se llena, descartar primero visitas repetidas y contabilizar descarte; no persistir credenciales ni usar almacenamiento local de usuario para eventos. El cierre del navegador puede perder datos: no garantiza entrega. Backend usa outbox durable con paginación, no esa cola volátil.

Reintentos propuestos: conexión/timeouts/5xx con backoff 1, 2, 4, 8 segundos hasta máximo 60 segundos y jitter; respetar Retry-After en 429. Tras diez fallos consecutivos, mover el registro saneado a cola de fallos y alertar, sin borrar la orden ni el evento durable. Errores 4xx de contrato no se reintentan sin corrección; 401/403 requieren resolver autorización. La política ante fallo de escritura de outbox transaccional necesita aprobación operativa: no confundir fallo de red del despachador con fallo de la transacción.

Deduplicar por eventId: mismo ID/contenido normalizado es repetición sin nuevo conteo; mismo ID/contenido diferente es conflicto. La idempotencia HTTP de órdenes es una dependencia distinta: eventId no evita por sí solo que se creen dos órdenes. Medir retraso, profundidad de cola, invalidaciones, reintentos y descartes mediante métricas operativas saneadas, sin incorporar nuevos event_type al catálogo aprobado.

### Throttle y debounce

- Órdenes, merma, precios, rechazos y cruces: sin sampling, throttle o debounce que borre hechos de negocio. Deduplicar únicamente reentregas del mismo eventId.
- section_viewed: un evento por transición real a la sección, no por rerender. Throttle de duplicados técnicos de la misma sección/sesión durante un segundo; no eliminar visitas después de salir y volver.
- workflow_started: una vez por workflow_id al primer cambio; no capturar pulsaciones. Deshabilitar envío repetido del mismo inicio no borra un nuevo flujo.
- frontend_error_detected: primer error de una firma controlada por sección/versión/sesión cada 60 segundos; contabilizar supresiones mediante métrica técnica, no afirmar conteo completo de errores. No debounce infinito que oculte un fallo persistente.
- api_request_completed: conservar errores y medir todas las solicitudes inicialmente. Si costo exige sampling de éxitos, cambiar explícitamente el contrato para registrar tasa de muestreo y evitar métricas sesgadas; no aplicar sampling oculto en 1.0.0.
- Alertas, no eventos: agregar episodios en ventanas de cinco minutos; enfriar notificaciones repetidas durante 15 minutos mientras persista el mismo episodio. Umbrales de tasa de error/latencia/login requieren aprobación y volumen mínimo, no una alerta por cada evento.
- No se propone debounce de búsquedas: no hay un evento de búsqueda aprobado. Las decisiones anteriores son defaults de diseño pendientes de aprobación operativa.

## 8. Almacenamiento, privacidad y retención

Propuesta: tabla de eventos válidos en PostgreSQL separada del inventario, con envelope, properties JSONB y eventId único. Metadatos de ingesta (received_at, productor verificado, procesamiento) son internos, fuera del envelope enviado. Índices: event_type/timestamp, requestId y producto/local/timestamp para inventario. No asumir orden de llegada; conservar fecha de ocurrencia y recepción.

Eventos inválidos/versiones desconocidas no entran al conjunto analítico válido. Una cuarentena restringida guarda solo representaciones saneadas, códigos de error y la correlación válida; nunca body original. Antes de enviar, construir properties seleccionando claves/valores permitidos; no capturar todo y confiar en limpiarlo al final. Aplicar un segundo control en ingesta. El patrón de una cadena no demuestra que carezca de PII.

No registrar nombres de empleados, clientes, correos, teléfonos, credenciales, tokens, IP, fingerprints, user-agent crudo, textos libres ni query strings. IDs opacos de usuario/sesión siguen siendo potencialmente vinculables: acceso restringido y eliminación por retención. Operaciones ve agregados por local; Lucía compras; Mariana consolidados; Jake señales de trazabilidad con permisos específicos. Acceso a crudos excepcional, auditable y limitado. Solo agregados sin identidad deben alimentar reportes ejecutivos.

Retención propuesta para aprobación: crudos 90 días; cuarentena saneada 7 días; agregados sin IDs de usuario/sesión 12 meses. Considerar auditoría, legislación aplicable, backups, eliminación de colas y costos antes de fijar estos plazos. La agregación conservada limita posteriores recalculados cuando ya se eliminaron los crudos; documentar esa restricción. No hay TTL implementado en esta entrega.

## 9. Reportes y agregación futura

- Compras: cantidades y montos por producto, proveedor, local, país, categoría y moneda. No sumar COP y USD como un único importe.
- Consumo: volumen por producto/local/unidad. No sumar kg, litros y unidades como magnitud única; excluir merma del consumo de cocina.
- Merma: cantidad por causa/local/producto. No publicar valor monetario sin método de valoración ni porcentaje sin denominador aprobado.
- Umbrales: cruces por producto/local y semana; no contar lecturas repetidas como episodios nuevos.
- Precios: referencia, variación y cobertura de entradas con costo/proveedor válido. Ausencia de eventos con cobertura incompleta no demuestra estabilidad.
- Uso y seguridad: visitas, conversión y fallos agregados. No identificar correos intentados ni convertir cancelación en abandono.
- Salud: percentiles de duración y tasa de error por ruta/fuente. No mezclar proxy/backend para duplicar peticiones. Configurar denominadores, ventana y volumen mínimo antes de alertar.

Guardar UTC; derivar día/semana por zona IANA del local validada en el catálogo. Semana propuesta: ISO, lunes-domingo en hora local, con año y número de semana ISO. Documentar cortes y comparabilidad en reportes por país; nunca usar idioma UI como país/zona horaria. Eventos tardíos actualizan su período y la inferencia de abandono; ventana de cierre/reprocesamiento requiere aprobación. Los reportes de ventas no pueden derivarse de consumo de ingredientes sin datos adicionales de ventas.

## 10. Riesgos y exclusiones

| Riesgo | Mitigación o límite |
| --- | --- |
| Ausencia de datos de precio/local/merma | Bloquear eventos dependientes y medir cobertura; no fabricar información |
| Stock global o salidas concurrentes | Resolver cálculo por local y consistencia transaccional antes de instrumentar cruces |
| Pérdidas de browser o TinyDB | Declarar entrega limitada, medir fallos y decidir persistencia apropiada por origen |
| Duplicados, reordenamiento y eventos tardíos | eventId estable, deduplicación, timestamp de ocurrencia y reprocesamiento |
| Alto volumen/costo de API y errores | Lotes acotados, agregación de alertas, throttle explícito de errores UI y revisión de sampling versionado |
| Confundir país, idioma, categorías o estados históricos | Catálogos autoritativos y mapeos explícitos; validar versiones |
| Pseudónimos o datos comerciales expuestos | Allowlist en origen/ingesta, acceso por rol, retención y auditoría |
| Alertas ruidosas o sin cobertura | Episodios agregados y reporte de cobertura; no asumir que cero eventos implica cero problemas |

| Evento o dato considerado y descartado de 1.0.0 | Razón |
| --- | --- |
| stock_read como evidencia de umbral | Lecturas repetidas inflan episodios; usar cruce real tras movimiento |
| workflow_abandoned emitido al cerrar pestaña | Señal no fiable; derivar con ventana de 30 minutos y reconciliación |
| keystroke_recorded, mouse_moved, payload completo de formulario | Alto volumen y riesgo de capturar credenciales/clientes; intención se mide sin contenido |
| session_expired desde cualquier 401 | 401 puede significar credencial inválida o sesión ausente; un evento separado requiere diagnóstico inequívoco, no se añade al catálogo aprobado |
| page_load_recorded | Considerado para rendimiento frontend futuro; definir full navigation frente a navegación SPA y decisión/SLA antes de ampliar el contrato; API y errores cubren la primera prioridad técnica |
| language_changed mezclado con country | Idioma no identifica país; evento UI separado fuera del objetivo de inventario actual |
| sales_recorded o conversiones de monedas | No hay fuente de ventas verificada; reporting ejecutivo, no telemetría, decide conversiones |
| Datos de cliente, nombre de empleado, texto de incidencia o stack libre | No necesarios para las decisiones del catálogo; riesgo de PII y secretos |

Estas exclusiones no limitan el futuro catálogo a un mínimo; explican por qué esos candidatos no son capturas fiables o justificadas en esta versión.

## 11. Versionado, validación y entrega

Clave de contrato: event_type/schemaVersion. Los contratos publicados son inmutables. Con allowlists cerradas, añadir campos requiere nueva versión y consumidores compatibles. Cambios de significado/tipo/obligatoriedad requieren migración explícita. Mantener versiones anteriores mientras existan productores activos; el archivo actual solo valida 1.0.0. Un default de JSON Schema es anotación, no inserción automática.

Revisar sintaxis y metaschema Draft 2020-12, referencias, cobertura de 22 eventos, descripciones y cierre de propiedades. Habilitar FormatChecker o equivalente para UUID/date-time; rechazar NaN/Infinity porque no son JSON válido. Comprobar ejemplos válidos/inválidos y relaciones de negocio en la fase de verificación: el esquema no puede comparar dinámicamente cantidades, precios, estados previos o identidad con la base.

La instrumentación posterior debe demostrar captura -> almacenamiento para los seis obligatorios, incluyendo reintentos y fallos. Datos semilla futuros: 8-10 productos de tres categorías; tres locales con CO y Florida; 15-20 entradas de al menos tres proveedores; 15-20 salidas con tres mermas de causas distintas; dos cruces de stock y una variación de precio. Usar datos existentes o carpetas de datos; no personas reales ni edición directa de stock. Reabastecer antes del segundo cruce y disponer de tres precios históricos antes de probar variación.

PR posterior hacia main con título **docs: telemetry design plan**. Su descripción incluirá 22 eventos (6 obligatorios, 16 identificados), categorías cubiertas y la decisión más difícil: representar hechos por local sin inventar datos que el sistema actual aún no registra. Commit descriptivo en español; no publicar hasta aprobación del paso correspondiente. El merge lo realiza manualmente el usuario.

Pendientes antes de implementación: aprobar cambios de modelos/rechazos, verificar catálogo de locales y unidades, acordar parámetros operativos/retención/alertas/cierre de reportes y demostrar consistencia transaccional por local. Ningún pendiente equivale a autorización de instrumentación en esta fase.