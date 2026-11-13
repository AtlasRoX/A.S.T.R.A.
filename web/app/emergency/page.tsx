import type { Metadata } from 'next';
import { EmergencyRunner } from '@/components/emergency/EmergencyRunner';
import { getCatalog } from '@/lib/engine';
import { getSession } from '@/lib/session';

export const metadata: Metadata = { title: 'Emergency' };

export default async function EmergencyPage() {
  const { crew, env } = await getSession();
  const catalog = await getCatalog();
  const me = catalog.crew.find((c) => c.id === crew) ?? catalog.crew[0];
  const environment = catalog.environments.find((e) => e.id === env) ?? catalog.environments[0];
  return (
    <div className="page">
      <EmergencyRunner protocols={catalog.protocols} crew={catalog.crew} me={me} env={environment} />
    </div>
  );
}
