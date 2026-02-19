<script lang="ts">
  import type { ICandidate, IContestReport } from '$lib/server/report_types';

  import tippy from 'tippy.js';
  import type { Props } from 'tippy.js';
  import { followCursor } from 'tippy.js';
  import 'tippy.js/themes/light-border.css';
  import 'tippy.js/dist/tippy.css';
  interface Props_1 {
    report: IContestReport;
  }

  // Avoid capturing the initial `report` value only; derive from props.
  let props_1: Props_1 = $props();
  let report = $derived.by(() => props_1.report);

  function tooltip(elem: Element, content: string | null): void {
    if (content === null) {
      return;
    }
    let props: Props = {
      ...({} as any as Props),
      content,
      allowHTML: true,
      theme: 'light-border',
      plugins: [followCursor],
      followCursor: true,
    };
    tippy(elem, props);
  }

  const outerHeight = 24;
  const innerHeight = 14;
  const labelSpace = 130;
  const width = 600;

  // Sort candidates by votes in descending order
  let candidates: ICandidate[] = $derived.by(() => [...report.candidates].sort((a, b) => b.votes - a.votes));

  let ballotsCast: number = $derived.by(() => report.ballotCount);
  // Scale based on 100% of ballots cast (theoretical maximum in approval voting)
  let scale = $derived.by(() => (width - labelSpace - 50) / ballotsCast);

  let height = $derived.by(() => outerHeight * candidates.length);

  // Color scheme for different approval counts (lighter for more approvals, starting with theme base)
  const approvalColors = {
    1: '#437527', // Theme's base green for single approval (strongest endorsement)
    2: '#5a8a35', // Lighter for two approvals
    3: '#6fa142', // Even lighter for three approvals
    4: '#84b84f', // Light green for four approvals
    5: '#99cf5c', // Very light green for five approvals
    6: '#aee669', // Lightest green for six approvals
    7: '#c3fd76', // Even lighter for seven approvals
    8: '#c3fd76', // Repeat lightest for eight approvals
  };

  // Get color for approval count, with fallback for higher counts
  function getApprovalColor(approvalCount: number): string {
    return approvalColors[approvalCount as keyof typeof approvalColors] || '#c3fd76';
  }

  // Generate bar segments for a candidate based on approval distribution
  function generateBarSegments(candidate: ICandidate) {
    const segments: Array<{
      width: number;
      color: string;
      approvalCount: number;
      voteCount: number;
    }> = [];

    if (!report.votingPatterns?.candidateApprovalDistributions?.[candidate.name]) {
      // Fallback to solid bar if no distribution data
      return [{
        width: scale * candidate.votes,
        color: '#437527',
        approvalCount: 0,
        voteCount: candidate.votes
      }];
    }

    const distribution = report.votingPatterns.candidateApprovalDistributions[candidate.name];
    let currentX = 0;

    // Sort approval counts in ascending order so 1-vote ballots appear on the left
    const sortedApprovals = Object.keys(distribution)
      .map(Number)
      .sort((a, b) => a - b);

    for (const approvalCount of sortedApprovals) {
      const voteCount = distribution[approvalCount];
      const segmentWidth = scale * voteCount;

      segments.push({
        width: segmentWidth,
        color: getApprovalColor(approvalCount),
        approvalCount,
        voteCount
      });
    }

    return segments;
  }
</script>

<svg width="100%" viewBox={`0 0 ${width} ${height}`}>
  <g transform={`translate(${labelSpace} 0)`}>
    <!-- 100% reference line -->
    <line
      x1={scale * ballotsCast}
      y1={0}
      x2={scale * ballotsCast}
      y2={height}
      stroke="#666"
      stroke-width="1"
      stroke-dasharray="2,2"
      opacity="0.5"
    />
    {#each candidates as candidate, i}
      <g
        class={candidate.winner === true ? '' : 'eliminated'}
        transform={`translate(0 ${outerHeight * (i + 0.5)})`}
      >
        <text 
          font-size="90%" 
          text-anchor="end" 
          dominant-baseline="middle"
          use:tooltip={`<strong>${candidate.name}</strong><br/>
          <strong>${candidate.votes.toLocaleString()}</strong> total votes<br/>
          ${((candidate.votes / ballotsCast) * 100).toFixed(1)}% of all ballots cast`}
        >
          {candidate.name}
        </text>
        <g transform={`translate(5 ${-innerHeight / 2 - 1})`}>
          {#each generateBarSegments(candidate) as segment, segmentIndex}
            <rect
              height={innerHeight}
              width={segment.width}
              x={segmentIndex === 0 ? 0 : generateBarSegments(candidate).slice(0, segmentIndex).reduce((sum, s) => sum + s.width, 0)}
              fill={segment.color}
              use:tooltip={segment.approvalCount > 0 ? `<strong>${candidate.name}</strong><br/>
              <strong>${segment.voteCount.toLocaleString()}</strong> votes from ballots with <strong>${segment.approvalCount}</strong> approval${segment.approvalCount === 1 ? '' : 's'}<br/>
              ${((segment.voteCount / candidate.votes) * 100).toFixed(1)}% of ${candidate.name}'s total votes` : `<strong>${candidate.name}</strong><br/>
              <strong>${candidate.votes.toLocaleString()}</strong> total votes<br/>
              ${((candidate.votes / ballotsCast) * 100).toFixed(1)}% of all ballots cast`}
            />
          {/each}
        </g>
        <text font-size="90%" dominant-baseline="middle" x={10 + scale * candidate.votes}>
          {((candidate.votes / ballotsCast) * 100).toFixed(1)}%</text
        >
      </g>
    {/each}
  </g>
</svg>

<style>
  .eliminated {
    opacity: 30%;
  }

  @media (prefers-color-scheme: dark) {
    text {
      fill: #e0e0e0;
    }
  }
</style>
