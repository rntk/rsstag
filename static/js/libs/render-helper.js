import { createRoot } from 'react-dom/client';

export function renderToRoot(containerId, element) {
  const container = document.getElementById(containerId);
  if (!container) return null;
  const root = createRoot(container);
  root.render(element);
  return root;
}
