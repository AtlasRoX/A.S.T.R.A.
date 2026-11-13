import { redirect } from 'next/navigation';
import { getSession } from '@/lib/session';

/**
 * Missions is no longer a page of its own: the game lives with the person (Progress on their profile) and with the
 * crew (the crew operation and rewards on the Crew page). Old links, the Alerts log's rewards and the assistant's
 * "Open your progress" action all land here and go to your own Progress section.
 */
export default async function MissionsPage() {
  const { crew } = await getSession();
  redirect(`/crew/${crew}#progress`);
}
