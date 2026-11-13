import type { Metadata, Viewport } from 'next';
import { Google_Sans, Google_Sans_Code } from 'next/font/google';
import { EngineOffline } from '@/components/EngineOffline';
import { Shell } from '@/components/shell/Shell';
import { MotionProvider } from '@/components/ui/MotionProvider';
import { ToastProvider } from '@/components/ui/Toast';
import { getAttention, getCatalog, getClock, getComms, getRoutine } from '@/lib/engine';
import { getSession } from '@/lib/session';
import './globals.css';
import './toast.css';

const sans = Google_Sans({ subsets: ['latin'], variable: '--font-google-sans', display: 'swap', adjustFontFallback: false });
const mono = Google_Sans_Code({
  subsets: ['latin'],
  variable: '--font-google-sans-code',
  display: 'swap',
  adjustFontFallback: false,
});

export const metadata: Metadata = {
  title: { default: 'ASTRA · Crew health', template: '%s · ASTRA' },
  description:
    'ASTRA (Astronaut Self-Triage & Readiness Assistant) helps astronauts on long-duration missions measure, ' +
    'understand and act on their own health.',
  applicationName: 'ASTRA',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  colorScheme: 'dark light',
  themeColor: [
    { media: '(prefers-color-scheme: dark)', color: '#05080f' },
    { media: '(prefers-color-scheme: light)', color: '#f3f5fa' },
  ],
};

// Apply the saved (or system) theme before first paint to avoid a flash.
const themeScript = `(function(){try{var t=localStorage.getItem('astra-theme');if(t!=='light'&&t!=='dark'){t=window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'}document.documentElement.dataset.theme=t}catch(e){document.documentElement.dataset.theme='dark'}})();`;

async function loadShell(crew: string, env: string) {
  const [catalog, clock, routine, attention, comms] = await Promise.all([
    getCatalog(),
    getClock(),
    getRoutine(crew, env),
    getAttention(crew, env).catch(() => null),
    getComms(env, crew).catch(() => null),
  ]);
  const due = routine.tasks.filter((t) => t.state === 'due' || t.state === 'overdue').length;
  return { catalog, clock, due, attentionCounts: attention?.counts ?? null, comms };
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  let data: Awaited<ReturnType<typeof loadShell>> | null = null;
  let offline = '';
  try {
    data = await loadShell(session.crew, session.env);
  } catch (e) {
    offline = e instanceof Error ? e.message : 'ASTRA Core is unreachable.';
  }
  const content = data ? (
    <Shell
      crew={data.catalog.crew}
      envs={data.catalog.environments}
      crewId={session.crew}
      envId={session.env}
      clock={data.clock}
      dueCount={data.due}
      attentionCounts={data.attentionCounts}
      comms={data.comms}
      mission={data.catalog.mission.name}
    >
      {children}
    </Shell>
  ) : (
    <EngineOffline message={offline} />
  );

  return (
    <html lang="en" data-theme="dark" className={`${sans.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <MotionProvider>
          <ToastProvider>{content}</ToastProvider>
        </MotionProvider>
      </body>
    </html>
  );
}
