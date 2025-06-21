import type { SVGProps } from 'react';

export function ItemRadarLogo(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 140 24"
      fill="none"
      aria-label="ItemRadar Logo"
      role="img"
      {...props}
    >
      <circle cx="12" cy="12" r="10" className="fill-primary" />
      <path
        d="M12 6L12 18M6 12L18 12"
        stroke="hsl(var(--primary-foreground))"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <text
        x="30"
        y="17"
        fontFamily="Inter, sans-serif"
        fontSize="16"
        fontWeight="bold"
        className="fill-foreground"
      >
        ItemRadar
      </text>
    </svg>
  );
} 