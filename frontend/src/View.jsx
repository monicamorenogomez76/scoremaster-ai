import React from 'react';

export function View({ name, active, eyebrow, title, description, action, children }) {
  return <section className={'app-view' + (active === name ? ' is-active' : '')} data-view={name}>
    <header className="view-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="view-description">{description}</p></div>{action}</header>
    {children}
  </section>;
}
