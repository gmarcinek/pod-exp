import { marked } from "marked";

type MarkdownContentProps = {
  content: string;
};

marked.setOptions({
  async: false,
});

export function MarkdownContent({ content }: MarkdownContentProps) {
  const html = marked.parse(content) as string;

  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}