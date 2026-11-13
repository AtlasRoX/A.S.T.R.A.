import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="page" style={{ display: 'grid', placeItems: 'center', minHeight: '60vh' }}>
      <div className="card" style={{ maxWidth: 480, textAlign: 'center', padding: 32 }}>
        <span className="overline">Signal lost</span>
        <h1 className="h-page" style={{ margin: '8px 0 10px' }}>
          Page not found
        </h1>
        <p className="muted" style={{ marginBottom: 20 }}>
          That screen isn&apos;t part of ASTRA. Head back to your overview.
        </p>
        <Link href="/" className="btn btn-primary">
          Back to overview
        </Link>
      </div>
    </div>
  );
}
