import React from "react";
import type { SVGProps } from "react";

type DocumentAnswerIconProps = Readonly<SVGProps<SVGSVGElement>>;

export function DocumentAnswerIcon({ className, ...props }: DocumentAnswerIconProps) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      data-testid="document-answer-icon"
      focusable="false"
      viewBox="0 0 220 180"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <ellipse className="document-answer-icon__base" cx="104" cy="158" rx="64" ry="10" />
      <path
        className="document-answer-icon__paper"
        d="M58 24h76l30 30v76c0 8.3-6.7 15-15 15H58c-8.3 0-15-6.7-15-15V39c0-8.3 6.7-15 15-15Z"
      />
      <path className="document-answer-icon__fold" d="M134 25v21c0 5 4 9 9 9h20" />
      <path className="document-answer-icon__line document-answer-icon__line--long" d="M68 70h63" />
      <path className="document-answer-icon__line" d="M68 88h72" />
      <path className="document-answer-icon__line" d="M68 106h52" />
      <path className="document-answer-icon__line document-answer-icon__line--soft" d="M68 124h37" />
      <path
        className="document-answer-icon__bubble"
        d="M93 96h67c12.2 0 22 9.8 22 22v8c0 12.2-9.8 22-22 22h-29l-19 16v-16H93c-12.2 0-22-9.8-22-22v-8c0-12.2 9.8-22 22-22Z"
      />
      <circle className="document-answer-icon__dot" cx="111" cy="123" r="4.6" />
      <circle className="document-answer-icon__dot" cx="128" cy="123" r="4.6" />
      <circle className="document-answer-icon__dot" cx="145" cy="123" r="4.6" />
      <path className="document-answer-icon__spark" d="M184 42l5.6 11.4L201 59l-11.4 5.6L184 76l-5.6-11.4L167 59l11.4-5.6L184 42Z" />
      <path className="document-answer-icon__spark document-answer-icon__spark--quiet" d="M35 86l3 6 6 3-6 3-3 6-3-6-6-3 6-3 3-6Z" />
      <circle className="document-answer-icon__spark document-answer-icon__spark--quiet" cx="184" cy="106" r="3.5" />
    </svg>
  );
}
