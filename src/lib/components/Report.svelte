<script lang="ts">
  import { resolve } from '$app/paths';

  import type { IContestReport, Allocatee, ICandidate } from '$lib/server/report_types';
  import VoteCounts from './report_components/VoteCounts.svelte';
  import ApprovalDistribution from './report_components/ApprovalDistribution.svelte';
  import CoApprovalMatrixSimple from './report_components/CoApprovalMatrixSimple.svelte';
  import AnyoneButAnalysis from './report_components/AnyoneButAnalysis.svelte';

  import { setContext } from 'svelte';

  interface Props {
    report: IContestReport;
  }

  // Avoid capturing the initial `report` value only; derive from props.
  let props: Props = $props();
  let report = $derived.by(() => props.report);

  function getCandidate(cid: Allocatee): ICandidate {
    return report.candidates[cid];
  }

  function getWinners(candidates: ICandidate[]): ICandidate[] {
    if (candidates.length == 1) {
      return [report.candidates[0]];
    }

    return candidates
      .filter((candidate) => candidate.winner === true)
      .sort((a, b) => b.votes - a.votes); // Sort by vote count descending (highest first)
  }

  setContext('candidates', {
    getCandidate,
  });

  function formatDate(dateStr: string): string {
    let date = new Date(dateStr);
    const months = [
      'January',
      'February',
      'March',
      'April',
      'May',
      'June',
      'July',
      'August',
      'September',
      'October',
      'November',
      'December',
    ];

    return `${months[date.getUTCMonth()]} ${date.getUTCDate()}, ${date.getUTCFullYear()}`;
  }

  let sumVotes = $derived.by(() =>
    report.candidates.map((candidate) => candidate.votes).reduce((a, b) => a + b)
  );

  let numCandidates = $derived.by(() =>
    report.candidates.filter((candidate) => !candidate.writeIn).length
  );
</script>

<div class="row">
  <p class="description"></p>
  <div class="electionHeader">
    <h1>
      <a href="{resolve('/', {})}">approval.vote</a>
      //
      <strong>{report.info.jurisdictionName}</strong>
      {report.info.officeName}
    </h1>
  </div>
</div>

<div class="row">
  <div class="leftCol">
    <p>
      The
      {#if report.info.website}
        <a href={report.info.website}>
          {report.info.jurisdictionName}
          {report.info.electionName}
        </a>
      {:else}{report.info.jurisdictionName} {report.info.electionName}{/if}
      was held on
      <strong>{formatDate(report.info.date)}</strong>.
      {#each getWinners(report.candidates) as winner, i}
        {#if i == 0}
          <strong>{winner.name}</strong>
        {:else if i == report.winners.length - 1}
          , and
          <strong>{winner.name}</strong>
        {:else}
          ,
          <strong>{winner.name}</strong>
        {/if}
      {/each}

      {#if report.winners.length == 1}
        was the winner out of
      {:else}were the winners out of{/if}
      <strong>{numCandidates}</strong>
      {#if numCandidates == 1}candidate{:else}candidates{/if}. {#if report.info.notes}{report.info
          .notes}{/if}
    </p>
    <p>
      There were <strong>{report.ballotCount.toLocaleString()}</strong> ballots, with
      <strong>{sumVotes.toLocaleString()}</strong>
      approvals. There was an average of
      <strong>{(sumVotes / report.ballotCount).toFixed(1)}</strong> approvals per ballot in this race.
    </p>
  </div>
  <div class="rightCol">
    <VoteCounts {report} />
  </div>
</div>

{#if report.coApprovals && report.coApprovals.length > 0 && report.votingPatterns}
<div class="row">
  <div class="leftCol">
    <h2>Approval Distribution</h2>
    <p>
      This shows how many candidates voters approved, both overall and broken down by
      each candidate's supporters. This reveals whether some candidates attracted voters
      who approved multiple candidates versus those who approved fewer candidates.
      In approval voting, voters can select as many candidates as they wish.
    </p>
  </div>

  <div class="rightCol">
    <ApprovalDistribution
      candidates={report.candidates.map(c => c.name)}
      votingPatterns={report.votingPatterns}
    />
  </div>
</div>

<div class="row">
  <div class="leftCol">
    <h2>Co-Approval Matrix</h2>
    <p>
      For every pair of candidates, this table shows the fraction of voters who
      approved one candidate that also approved the other. This reveals voting
      patterns and candidate coalitions.
    </p>
  </div>

  <div class="rightCol">
    <CoApprovalMatrixSimple
      coApprovals={report.coApprovals}
      candidates={report.candidates.map(c => c.name)}
      votingPatterns={report.votingPatterns}
    />
  </div>
</div>

{#if report.votingPatterns?.anyoneButAnalysis}
<div class="row">
  <div class="leftCol">
    <h2>"Anyone But" Analysis</h2>
    <p>
      This shows which candidates were excluded when voters approved all candidates except one.
      These ballots reveal strong opposition patterns, where voters are saying
      "I'll support anyone except this candidate."
    </p>
    {#if report.votingPatterns?.anyoneButAnalysis}
      {@const totalExclusions = Object.values(report.votingPatterns.anyoneButAnalysis).reduce((sum, count) => sum + count, 0)}
      <p>
        <strong>{totalExclusions.toLocaleString()}</strong> ballots approved all but one candidate
        ({((totalExclusions / report.ballotCount) * 100).toFixed(1)}% of all ballots).
      </p>
    {/if}
  </div>

  <div class="rightCol">
    <AnyoneButAnalysis
      candidates={report.candidates.map(c => c.name)}
      votingPatterns={report.votingPatterns}
    />
  </div>
</div>
{/if}
{/if}
