import { usePostMortemDetail } from '../mosaic/PostMortemDetailContext';
import PostMortemChatPanel from '../PostMortemChatPanel';
import { useParams } from 'react-router-dom';

export default function ChatTile() {
  const { id } = useParams<{ id: string }>();
  const { postmortem } = usePostMortemDetail();

  if (!postmortem || !id) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: '13px' }}>
        Loading…
      </div>
    );
  }

  return (
    <div style={{ height: '100%', overflow: 'hidden' }}>
      <PostMortemChatPanel
        isOpen={true}
        onClose={() => {}}
        postMortemTitle={postmortem.title || 'Untitled Post-Mortem'}
        transactionCount={postmortem.transaction_count || 0}
        postMortemId={id}
        transactions={postmortem.transactions || []}
      />
    </div>
  );
}
