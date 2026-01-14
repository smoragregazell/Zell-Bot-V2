# Preguntas de Prueba para Sistema de Cotizaciones

## 1. Búsqueda por Contenido de Cotización (Búsqueda Semántica)

### Preguntas que buscan el contenido/tema de la cotización:

1. **"Busca cotizaciones sobre reportes de créditos"**
   - Debe encontrar cotizaciones relacionadas con reportes, créditos, etc.
   - Ejemplo esperado: "Reporte de Créditos", "Reporte Listado de créditos aperturado", etc.

2. **"¿Hay cotizaciones sobre integración de queries?"**
   - Debe encontrar: "Integrar Query Bursa a GOC", "Integrar Query Bursa a CFA"

3. **"Busca cotizaciones relacionadas con procesos de pago"**
   - Debe encontrar: "Proceso de Anulación de Pagos", "Req. relación de forma de pago directo x alerta"

4. **"Cotizaciones sobre calificaciones o matrices"**
   - Debe encontrar: "Proceso de Calificación Masiva (Matriz) INNODI"

5. **"Busca cotizaciones de reportes de auditoría"**
   - Debe encontrar: "Reporte Auditoria Innodi"

6. **"¿Qué cotizaciones hay sobre domiciliación?"**
   - Debe encontrar cotizaciones relacionadas con domiciliación, cuentas, etc.

7. **"Busca cotizaciones sobre buscadores o agendas"**
   - Debe encontrar: "Requerimiento Buscador Agendas"

8. **"Cotizaciones relacionadas con pantallas o revisiones"**
   - Debe encontrar: "Agregar opción Solicitudes pantalla Revisión"

9. **"¿Hay cotizaciones sobre dígitos verificadores?"**
   - Debe encontrar: "dígito verificador"

10. **"Busca cotizaciones sobre reportes de operaciones"**
    - Debe encontrar: "Reporte de Exigible vs pagos", "Configurar Reporte de Operaciones por Cliente"

---

## 2. Preguntas sobre Títulos y Unidades Específicas

### Preguntas que buscan información específica de campos:

11. **"Muéstrame la cotización del ticket 1054"**
    - Debe mostrar: Ticket 1054, Cotización 69, Título: "Requerimiento Buscador Agendas", Unidades: 2.0

12. **"¿Cuántas unidades tiene la cotización del ticket 1069?"**
    - Debe mostrar: Ticket 1069, Unidades: 4.0, Título: "dígito verificador"

13. **"Dame el título y unidades de la cotización 69"**
    - Debe mostrar: Título: "Requerimiento Buscador Agendas", Unidades: 2.0

14. **"¿Qué título tiene la cotización del ticket 1270?"**
    - Debe mostrar: "Proceso de Calificación Masiva (Matriz) INNODI"

15. **"Muéstrame las unidades de las cotizaciones sobre reportes"**
    - Debe buscar cotizaciones de reportes y mostrar sus unidades

16. **"¿Cuál es el título de la cotización 71?"**
    - Debe mostrar: "dígito verificador"

17. **"Dame la información completa de la cotización del ticket 1440"**
    - Debe mostrar: Ticket 1440, Quote ID 101, Título: "Integrar Query Bursa a GOC", Unidades: 2.0, Fecha: 2018-06-26

18. **"Busca la cotización con título 'Proceso de Anulación de Pagos' y muéstrame sus unidades"**
    - Debe mostrar: Unidades: 3.0

---

## 3. Pruebas de Conexión entre Tickets y Cotizaciones (Flujo Bidireccional)

### De Ticket a Cotización:

19. **"Muéstrame el ticket 1054"** 
    - Después de mostrar el ticket, el sistema debe PROPONER: "¿Te gustaría que busque la cotización relacionada a este ticket?"
    - Si el usuario dice "sí" o "busca la cotización", debe mostrar la cotización del ticket 1054

20. **"Dame el ticket 1069 y su cotización"**
    - El usuario indica explícitamente que quiere ambos
    - Debe mostrar ticket 1069 Y luego buscar/get_item de cotización 1069

21. **"Traeme el ticket 1270"**
    - Después de mostrar el ticket, cuando parezca que terminó, debe PROPONER buscar la cotización

22. **"Ticket 1440"**
    - Similar, debe mostrar el ticket y proponer la cotización después

### De Cotización a Ticket:

23. **"Busca cotizaciones sobre reportes de créditos"**
    - Después de mostrar resultados de cotizaciones, debe PREGUNTAR: "¿Te gustaría que busque la información completa del ticket [ID]?" para cada cotización relevante

24. **"Muéstrame la cotización del ticket 1054"**
    - Después de mostrar la cotización, debe PREGUNTAR: "¿Te gustaría que busque la información completa del ticket 1054?"

25. **"Dame la cotización 69"**
    - Después de mostrar, debe PREGUNTAR si quiere el ticket completo

26. **"Busca cotizaciones sobre procesos de pago"**
    - Después de mostrar resultados, debe PREGUNTAR para cada una si quiere el ticket

27. **"¿Qué cotización tiene el ticket 1069?"**
    - Debe mostrar la cotización y luego PREGUNTAR si quiere el ticket completo

28. **"Cotización del ticket 1223"**
    - Muestra cotización y pregunta por ticket

### Pruebas de Flujo Completo (Bidireccional):

29. **"Muéstrame el ticket 1054"** → Usuario: "sí, dame la cotización" → "Ahora dame el ticket completo otra vez"
    - Prueba: Ticket → Cotización → Ticket (usando el mismo ID)

30. **"Busca cotizaciones sobre integración"** → Usuario: "muéstrame el ticket del primero" → "Ahora busca su cotización de nuevo"
    - Prueba: Cotización → Ticket → Cotización (usando el mismo ID)

31. **"Ticket 1270 y su cotización"**
    - Usuario pide ambos explícitamente
    - Debe traer ticket Y cotización usando el mismo ID (1270)

32. **"Muéstrame la cotización del ticket 1440"** → Usuario: "dame el ticket completo"
    - Prueba flujo: Cotización → Ticket (usando i_issue_id = 1440)

### Pruebas de Negación (NO debe buscar automáticamente):

33. **"Muéstrame el ticket 1054"** → Usuario no responde nada
    - El sistema NO debe buscar la cotización automáticamente
    - Solo debe proponerla si parece que la conversación terminó

34. **"Busca cotizaciones sobre reportes"** → Usuario no responde sobre el ticket
    - El sistema NO debe buscar el ticket automáticamente
    - Debe preguntar primero

---

## Resumen de Escenarios de Prueba:

✅ **Búsqueda semántica** (10 preguntas): Prueba que encuentra cotizaciones por contenido/tema
✅ **Información específica** (8 preguntas): Prueba títulos, unidades, IDs específicos
✅ **Ticket → Cotización** (4 preguntas): Prueba propuesta después de mostrar ticket
✅ **Cotización → Ticket** (6 preguntas): Prueba pregunta antes de buscar ticket
✅ **Flujo bidireccional** (4 preguntas): Prueba saltos usando el mismo ID
✅ **Negación/NO automático** (2 preguntas): Prueba que NO busca automáticamente sin indicación del usuario

**Total: 34 preguntas de prueba**

