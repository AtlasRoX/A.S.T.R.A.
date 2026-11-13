import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { MeasureWizard } from '@/components/measure/MeasureWizard';
import { getCatalog, getDashboard } from '@/lib/engine';
import { getSession } from '@/lib/session';

export async function generateMetadata({ params }: { params: Promise<{ metric: string }> }): Promise<Metadata> {
  const { metric } = await params;
  const catalog = await getCatalog();
  return { title: `Measure ${catalog.metrics.find((m) => m.id === metric)?.label ?? ''}`.trim() };
}

export default async function MeasureMetricPage({
  params,
  searchParams,
}: {
  params: Promise<{ metric: string }>;
  searchParams: Promise<{ task?: string }>;
}) {
  const [{ metric: id }, { task: taskId }, { crew, env }] = await Promise.all([params, searchParams, getSession()]);
  const [catalog, d] = await Promise.all([getCatalog(), getDashboard(crew, env)]);
  const metric = catalog.metrics.find((m) => m.id === id);
  if (!metric) notFound();
  const task = taskId ? (d.routine.tasks.find((t) => t.id === taskId && t.metrics.includes(id)) ?? null) : null;
  const bundle = task
    ? task.metrics.map((mid) => ({ id: mid, label: catalog.metrics.find((m) => m.id === mid)?.label ?? mid }))
    : [];
  return (
    <div className="page">
      <MeasureWizard
        key={`${id}-${task?.id ?? 'adhoc'}`}
        metric={metric}
        state={d.metrics[id]}
        task={task}
        bundle={bundle}
        symptoms={catalog.symptoms}
        hazards={catalog.hazards.filter((h) => metric.hazards.includes(h.id))}
        env={d.env}
        contexts={catalog.contexts ?? []}
        escalation={catalog.escalation}
      />
    </div>
  );
}
