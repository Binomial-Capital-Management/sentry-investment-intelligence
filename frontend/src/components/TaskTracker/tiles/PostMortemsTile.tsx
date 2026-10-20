import { useReview } from '../mosaic/ReviewContext';
import { PostMortemsPanel } from '../PostMortems/PostMortemsPanel';

export default function PostMortemsTile() {
  const { tasks } = useReview();
  return (
    <div style={{ height: '100%', overflow: 'hidden' }}>
      <PostMortemsPanel tasks={tasks} viewMode="post_mortems" onViewChange={() => {}} />
    </div>
  );
}
