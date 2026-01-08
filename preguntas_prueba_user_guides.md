# Preguntas de Prueba para User Guides

## 🔍 BÚSQUEDAS ESPECÍFICAS POR PROCESO

1. **¿Cómo hacer reintentos de domiciliación en Zell?**
   - Debería encontrar: Guía #1 "Reintentos de domiciliacion"
   - Debería mostrar: pasos numerados (3.1, 3.2, etc.)

2. **¿Cuál es el proceso para crear una lista de reintentos de domiciliación?**
   - Debería encontrar: Guía #1
   - Debería mostrar: objetivo y pasos específicos

3. **¿Cómo configurar políticas de autorización de créditos?**
   - Debería encontrar: Guía #3 "Configuración de paquete de políticas"

4. **¿Cómo cambiar el estatus de un crédito cuando se aplica un pago?**
   - Debería encontrar: Guía #5 "Cambiar el estatus del credito por aplicación de pagos"

5. **¿Cómo cargar una tabla de amortización personalizada?**
   - Debería encontrar: Guía #6 "Cargar tabla de amortizacion personalizada"

---

## 📋 BÚSQUEDAS POR CONFIGURACIÓN

6. **¿Cómo configurar plantillas de Email y XML para envío?**
   - Debería encontrar: Guía #4 "Configuración de Email, documentos XML y formatos de documentos"

7. **¿Cómo configurar documentos para descarga?**
   - Debería encontrar: Guía #4 (relacionada con formatos de documentos)

8. **¿Cuáles son los pasos para configurar políticas?**
   - Debería encontrar: Guía #3

---

## 🎯 BÚSQUEDAS POR OBJETIVO O CONCEPTO

9. **¿Hay alguna guía sobre domiciliación?**
   - Debería encontrar: Guía #1 (búsqueda más amplia)

10. **¿Cómo se manejan los tickets en el sistema?**
    - Debería encontrar: Guía #2 "Tickets" (aunque puede mencionar que no está disponible)

11. **Necesito ayuda con tablas de amortización personalizadas**
    - Debería encontrar: Guía #6

---

## 📝 BÚSQUEDAS ESPECÍFICAS POR MÓDULO O PANTALLA

12. **¿Cómo ingresar al módulo de cobranza para domiciliación?**
    - Debería encontrar: Guía #1, específicamente el paso que menciona el módulo

13. **¿Dónde está el botón "Procesos" en domiciliación?**
    - Debería encontrar: Guía #1, pasos específicos sobre botones

14. **¿Cómo funciona el módulo de tickets?**
    - Debería encontrar: Guía #2

---

## 🔧 BÚSQUEDAS POR PASOS ESPECÍFICOS

15. **¿Cuál es el paso 3.1 para elaborar una lista de reintentos?**
    - Debería encontrar: Guía #1, paso 3.1 específico
    - IMPORTANTE: Debería mostrar TODO el documento completo cuando se llame get_item

16. **¿Qué sigue después del paso 3.1 en domiciliación?**
    - Debería encontrar: Guía #1, pasos siguientes (3.2, 3.3, etc.)

17. **¿Cuáles son todos los pasos para configurar políticas?**
    - Debería encontrar: Guía #3 con todos los pasos numerados

---

## 🧪 BÚSQUEDAS QUE NO DEBERÍAN USAR USER_GUIDES

18. **¿Cuál es la política de la empresa sobre ISO?**
    - NO debería usar user_guides, debería usar docs_org

19. **¿Qué se discutió en la última reunión semanal?**
    - NO debería usar user_guides, debería usar meetings_weekly

20. **¿En qué ticket se habló del problema X?**
    - NO debería usar user_guides, debería buscar en tickets

---

## 🎯 PRUEBAS ESPECÍFICAS DE FUNCIONALIDAD

21. **Muéstrame la guía completa de reintentos de domiciliación**
    - Debería: buscar la guía #1 y cuando se llame get_item, devolver TODO el documento completo

22. **Necesito ver todos los pasos para configurar políticas de crédito**
    - Debería: buscar la guía #3 y devolver el documento completo

23. **¿Cuál es el objetivo de la guía de reintentos de domiciliación?**
    - Debería: mostrar el objetivo de la guía #1 en metadata

24. **¿Qué ticket está relacionado con la configuración de Email y XML?**
    - Debería: mostrar la referencia_cliente_ticket (CRQ / Ticket 17509) de la guía #4

---

## 📌 CASOS EDGE (Límites)

25. **¿Cómo hacer algo que no existe en las guías?**
    - Debería: buscar pero no encontrar nada relevante, decir que no hay guías sobre ese tema

26. **Busca información sobre "configuración avanzada de módulos inexistentes"**
    - Debería: no encontrar resultados o resultados muy débiles

27. **¿Cómo configurar?** (pregunta muy genérica)
    - Debería: buscar pero probablemente devolver resultados mixtos o pedir más detalles

---

## ✅ CHECKLIST DE VERIFICACIÓN

Para cada pregunta, verifica:

- [ ] ¿Se activó el universo `user_guides` correctamente?
- [ ] ¿Los resultados muestran el `objetivo` de la guía?
- [ ] ¿Los resultados muestran `step_label` cuando hay pasos numerados?
- [ ] ¿Al llamar `get_item`, se devuelve TODO el documento completo (no solo chunks adyacentes)?
- [ ] ¿Los pasos están ordenados correctamente (3.1, 3.2, 3.3, etc.)?
- [ ] ¿Se muestra metadata como `doc_number`, `referencia_cliente_ticket`?
- [ ] ¿Para preguntas que NO son de guías, NO se usa `user_guides`?

---

## 🚀 PRUEBAS AVANZADAS

28. **Busca en las guías de usuario cómo hacer domiciliación**
    - Verificar que usa `universe="user_guides"` explícitamente

29. **¿Hay alguna guía que hable de amortización personalizada?**
    - Debería encontrar: Guía #6 y mostrar su objetivo

30. **Muéstrame todos los pasos de la guía de tickets**
    - Debería: devolver el documento completo con todos los pasos ordenados

