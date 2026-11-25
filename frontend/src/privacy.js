// The cookie notice, the permission to load YouTube and the privacy policy (2026-11-25). The policy tells what the app
// really does: it changes with it, and NOTICE with the cookies, so that everyone reads the notice again.
import { t } from './i18n.js';

export const VIEW = '#privacidad';
const NOTICE = '2026-11-25';
const NOTICE_KEY = 'scoremaster.cookie-notice', YOUTUBE_KEY = 'scoremaster.youtube';
const deviceStorage = () => { try { return globalThis.localStorage; } catch { return undefined; } };
const kept = (key, storage) => { try { return storage?.getItem(key) ?? null; } catch { return null; } };
const keep = (key, value, storage) => { try { if (value) storage?.setItem(key, value); else storage?.removeItem(key); } catch { /* only for this visit */ } };

export const noticeSeen = (storage = deviceStorage()) => kept(NOTICE_KEY, storage) === NOTICE;
export const seeNotice = (storage = deviceStorage()) => keep(NOTICE_KEY, NOTICE, storage);
export const youTubeAllowed = (storage = deviceStorage()) => kept(YOUTUBE_KEY, storage) === 'yes';
export const allowYouTube = (allowed, storage = deviceStorage()) => keep(YOUTUBE_KEY, allowed ? 'yes' : '', storage);

// [heading, [paragraph or list of items]] of each section. privacy: the controller and its contact, from the server.
export function policy(privacy) {
  const { controller, email } = privacy || {};
  return [
    [t('Quién responde de tus datos'), [
      controller ? t('Responsable: {controller}.', { controller }) : t('Los datos de la persona o entidad responsable de esta instalación todavía no se han publicado.'),
      ...(email ? [t('Contacto: {email}', { email })] : []),
    ]],
    [t('Qué datos se guardan'), [[
      t('Tu cuenta: nombre, email y la contraseña cifrada de forma que no se puede leer. Si entras con Google, el identificador de tu cuenta de Google.'),
      t('Lo que guardas en la app: partituras, bandas, conciertos, ensayos, correcciones y lo que escribas en ellos.'),
      t('Si te invitan a valorar pasajes: tu email, tu experiencia, tu instrumento y tus valoraciones. Las ve quien administra la campaña.'),
      t('Registro de seguridad: fecha, dirección IP y tipo de acceso (entrada, entrada fallida, cambio de contraseña).'),
    ]]],
    [t('Para qué se usan y por qué se puede'), [[
      t('Para darte el servicio que pides al crear la cuenta (ejecución de un contrato).'),
      t('Para proteger las cuentas frente a accesos indebidos (interés legítimo).'),
      t('Para comparar las valoraciones con el análisis, solo si decides participar en una campaña (consentimiento).'),
    ], t('No se venden, no se usan para publicidad y no hay decisiones automáticas sobre las personas.')]],
    [t('Quién más los trata'), [[
      t('Render (aloja la aplicación) y Neon (guarda la base de datos).'),
      t('Brevo: envía los correos de confirmación y de recuperación de la contraseña.'),
      t('GitHub: lee los PDF que subes; se borran de la aplicación al terminar la lectura.'),
      t('Google Gemini: solo si está activado y pides una explicación, una opinión o preguntas algo. Recibe el análisis de la obra y tu pregunta, no tu nombre ni tu email. En su nivel gratuito, Google puede usar lo enviado para mejorar sus productos.'),
      t('jsDelivr y gleitz.github.io: al pulsar Reproducir envían los sonidos de los instrumentos y reciben tu dirección IP.'),
      t('YouTube: solo si permites cargar sus vídeos. Al buscarlos, el servidor envía a YouTube el texto de la búsqueda.'),
    ], t('Algunos de estos proveedores son de Estados Unidos y pueden tratar los datos fuera del Espacio Económico Europeo.')]],
    [t('Cuánto tiempo'), [
      t('Tus datos se conservan mientras exista tu cuenta y el registro de seguridad, un año como máximo. La sesión caduca a los 7 días, el enlace de recuperación a los 30 minutos y el de confirmación a las 24 horas.'),
      t('Al borrar la cuenta se borran en el momento. Las copias de seguridad ya hechas pueden conservarlos hasta que se eliminen.')]],
    [t('Tus derechos'), [
      t('En Configuración › Privacidad puedes descargar tus datos y borrar tu cuenta.'),
      t('Puedes pedir el acceso a tus datos, su rectificación, supresión o portabilidad, y oponerte a su uso o limitarlo, escribiendo al contacto de esta página. También puedes reclamar ante la Agencia Española de Protección de Datos (www.aepd.es).')]],
    [t('Cookies y lo que se guarda en tu navegador'), [[
      t('scoremaster_session: mantiene tu sesión abierta. Técnica; 7 días o hasta que cierres la sesión.'),
      t('scoremaster_oauth: protege la entrada con Google. Técnica; 10 minutos.'),
      t('Almacenamiento del navegador: idioma, tema, tamaño del texto, compases por pentagrama, que has leído el aviso y si permites YouTube. No sale de tu dispositivo.'),
      t('YouTube: si permites sus vídeos, puede guardar datos en tu navegador. Puedes retirar el permiso en Configuración.'),
    ], t('No hay cookies de analítica ni de publicidad. Las técnicas no necesitan consentimiento.')]],
  ];
}
