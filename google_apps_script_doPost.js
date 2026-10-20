/**
 * Google Apps Script - Webhook para sincronización de Google Calendar
 * Sincroniza eventos de Masterclasses de Universidad.Online
 * 
 * INSTRUCCIONES:
 * 1. Entra a tu proyecto de Google Apps Script (donde creaste el Webhook).
 * 2. Reemplaza la función doPost(e) con este código.
 * 3. Haz clic en "Implementar" -> "Administrar implementaciones" -> Editar (ícono lápiz) -> "Nueva versión" -> "Implementar".
 */

function doPost(e) {
  try {
    var rawData = e.postData ? e.postData.contents : null;
    if (!rawData) {
      return ContentService.createTextOutput("ERROR: No se recibieron datos en la peticion POST");
    }

    var data = JSON.parse(rawData);
    var idClase = (data.id_clase || "").toString().trim();
    var titulo = (data.titulo || "").toString().trim();
    var inicioIso = data.inicio || "";
    var finIso = data.fin || "";

    if (!idClase || !titulo || !inicioIso || !finIso) {
      return ContentService.createTextOutput("ERROR: Faltan campos requeridos (id_clase, titulo, inicio, fin)");
    }

    var start = new Date(inicioIso);
    var end = new Date(finIso);

    // Obtener calendario por defecto del usuario
    var cal = CalendarApp.getDefaultCalendar();

    // Ventana amplia de búsqueda: 48 horas alrededor de la fecha del evento
    // (desde 24 horas antes del inicio hasta 48 horas despues)
    var ventanaInicio = new Date(start.getTime() - (24 * 60 * 60 * 1000));
    var ventanaFin = new Date(end.getTime() + (48 * 60 * 60 * 1000));

    // Obtener todos los eventos dentro de la ventana de 48+ horas
    var eventos = cal.getEvents(ventanaInicio, ventanaFin);
    var eventoEncontrado = null;

    // Buscar si ya existe un evento con este ID_CLASE en la descripción
    var idBuscado = idClase.toLowerCase();
    for (var i = 0; i < eventos.length; i++) {
      var desc = (eventos[i].getDescription() || "").toLowerCase();
      var evTitle = (eventos[i].getTitle() || "").toLowerCase();

      // Coincidencia por ID_CLASE en la descripcion o en el titulo
      if (desc.indexOf(idBuscado) !== -1 || desc.indexOf("id_clase: " + idBuscado) !== -1) {
        eventoEncontrado = eventos[i];
        break;
      }
    }

    var descripcionFinal = "ID_CLASE: " + idClase + "\nSincronizado automaticamente por Bot_UniversidadOnline";

    if (eventoEncontrado) {
      // ACTUALIZAR evento existente: reajusta horario exacto, título y descripción
      eventoEncontrado.setTitle(titulo);
      eventoEncontrado.setTime(start, end);
      eventoEncontrado.setDescription(descripcionFinal);
      return ContentService.createTextOutput("ACTUALIZADO");
    } else {
      // CREAR nuevo evento si no existía previamente
      cal.createEvent(titulo, start, end, {
        description: descripcionFinal
      });
      return ContentService.createTextOutput("CREADO");
    }

  } catch (err) {
    return ContentService.createTextOutput("ERROR: " + err.toString());
  }
}
