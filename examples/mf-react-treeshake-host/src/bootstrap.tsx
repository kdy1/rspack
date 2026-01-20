import React, { Suspense, lazy } from 'react';
import { createRoot } from 'react-dom/client';

// Lazy load the remote App component
// This will trigger the fallback file loading for ui-lib
// since the host doesn't share ui-lib
const RemoteApp = lazy(() => import('remote/App'));

function App() {
  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
      <h1>Host App - Module Federation Tree Shaking Test</h1>
      <p>
        This host app loads a remote that uses <code>ui-lib</code>.
        Since the host doesn't share <code>ui-lib</code>, the remote will use its
        <strong> fallback file</strong>.
      </p>
      <p>
        The fallback file should be tree-shaken by the secondary tree-shaking service,
        only including <code>Button</code> and <code>Badge</code> components.
      </p>
      <hr style={{ margin: '20px 0' }} />
      <h2>Remote App:</h2>
      <Suspense fallback={<div>Loading remote app...</div>}>
        <RemoteApp />
      </Suspense>
    </div>
  );
}

const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(<App />);
}
