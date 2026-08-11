import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * One place to configure markdown, so the chat and the weekly report can't
 * drift apart.
 *
 * remark-gfm is what makes tables work. Tables are a GitHub-flavoured
 * extension, not core markdown, so without it react-markdown passes them
 * through as literal text and the model's neat daily breakdown arrives as a
 * wall of pipe characters.
 *
 * The table wrapper matters just as much on a 390px phone: a date/steps table
 * is wider than the screen, and it has to scroll inside its own box rather
 * than making the whole page scroll sideways.
 */
export default function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        table: ({ node: _node, ...props }) => (
          <div className="md-table-wrap">
            <table {...props} />
          </div>
        ),
      }}
    >
      {children}
    </ReactMarkdown>
  )
}
