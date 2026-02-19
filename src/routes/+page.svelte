<script lang="ts">
  import { resolve } from '$app/paths';
  import type { IElectionIndexEntry } from '$lib/server/report_types';

  interface Props {
    data: import('./$types').PageData;
  }

  let props: Props = $props();

  // Avoid capturing the initial `data` value only; derive from props for client-side navigation.
  type IndexByYear = Map<string, IElectionIndexEntry[]>;
  let index: IndexByYear = $derived.by(() => props.data.index as IndexByYear);

  // Calculate total statistics (using reduce to avoid mutation warnings)
  type Stats = { totalRaces: number; totalApprovals: number; totalBallots: number };
  let stats: Stats = $derived.by((): Stats => {
    return Array.from(index.entries()).reduce<Stats>(
      (acc, [_year, elections]) => {
        elections.forEach((election) => {
          election.contests.forEach((contest) => {
            acc.totalRaces++;
            acc.totalApprovals += contest.sumVotes || 0;
            acc.totalBallots += contest.ballotCount || 0;
          });
        });
        return acc;
      },
      { totalRaces: 0, totalApprovals: 0, totalBallots: 0 }
    );
  });

  let totalRaces = $derived.by(() => stats.totalRaces);
  let totalApprovals = $derived.by(() => stats.totalApprovals);
  let totalBallots = $derived.by(() => stats.totalBallots);

  let avgApprovalsPerBallot = $derived.by(() =>
    totalBallots > 0 ? (totalApprovals / totalBallots).toFixed(1) : '0.0'
  );
</script>

<svelte:head>
  <title>approval.vote: detailed reports on approval voting elections.</title>
  <meta
    name="description"
    content="Explore detailed reports and analysis of approval voting elections. See how voters express their preferences when they can choose multiple candidates."
  />

  <!-- Open Graph Tags -->
  <meta property="og:type" content="website" />
  <meta
    property="og:title"
    content="approval.vote: Detailed Reports and Analysis of Approval Voting Elections"
  />
  <meta
    property="og:description"
    content="Explore comprehensive reports and analysis of approval voting elections from across the United States. See how voters express their preferences when they can choose multiple candidates, with detailed visualizations of vote counts, co-approval patterns, and voting distributions."
  />
  <meta property="og:url" content="https://approval.vote" />
  <meta property="og:image" content="https://approval.vote/images/index.png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:image:type" content="image/png" />

  <!-- Twitter Tags -->
  <meta name="twitter:title" content="approval.vote: Detailed Reports and Analysis of Approval Voting Elections" />
  <meta
    name="twitter:description"
    content="Explore comprehensive reports and analysis of approval voting elections from across the United States. See how voters express their preferences when they can choose multiple candidates."
  />
  <meta name="twitter:image" content="https://approval.vote/images/index.png" />
  <meta name="twitter:image:width" content="1200" />
  <meta name="twitter:image:height" content="630" />
  <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "WebSite",
      "name": "approval.vote",
      "description": "Detailed reports on approval voting elections",
      "url": "https://approval.vote",
      "author": {
        "@type": "Person",
        "name": "Felix Sargent",
        "url": "https://felixsargent.com"
      }
    }
  </script>
</svelte:head>

<div class="wide container">
  <div class="row">
    <div class="leftCol">
      <div class="description">
        <h1>approval.vote:</h1> detailed reports on approval voting elections.
      </div>
      <p>
        With <a href="{resolve('/about-approval-voting', {})}"> Approval Voting</a> voters can choose as many candidates
        as they like, and the one receiving the most votes wins.
      </p>

      <p>
        This site contains detailed reports on <strong>{totalRaces}</strong> approval voting races.
        Across all elections, voters selected an average of <strong>{avgApprovalsPerBallot}</strong>
        candidates per ballot.
      </p>

      <p>
        <strong>approval.vote</strong> is a project of
        <a href="https://felixsargent.com">Felix Sargent</a>. It is a fork of
        <a href="https://paulbutler.org">Paul Butler's</a>
        <a href="https://ranked.vote">ranked.vote</a>. It is non-partisan and has received no
        outside funding.
      </p>
      <p>
        For more information, see
        <a href="{resolve('/about', {})}">the about page</a>, learn about
        <a href="{resolve('/about-approval-voting', {})}">approval voting</a>, compare
        <a href="{resolve('/rcv-vs-approval', {})}">RCV vs approval voting</a>, or design your own system with
        the <a href="{resolve('/voting-method-finder', {})}">voting method finder</a>.
        You can also browse the underlying database on <a href="{resolve('/data', {})}">the data page</a>.
      </p>

      <p>
        View the source code on
        <a href="https://github.com/electionscience/approval-vote">GitHub</a>.
      </p>
    </div>

    <div class="rightCol">
      {#each [...index] as [year, elections]}
        <div class="yearSection">
          <h2>{year}</h2>
          <div class="electionSection">
            {#each elections as election}
              <div class="electionHeader">
                <h3>
                  <strong>{election.jurisdictionName}</strong>
                  {election.electionName}
                </h3>
              </div>
              {#each election.contests as contest}
                <div class="race">
                  <a href="{resolve(`/report/${election.path}/${contest.office}`, {})}">
                    <div class="race-content">
                      <div class="title">
                        <strong>{contest.officeName}</strong>
                        {#each contest.winners as winner, i}
                          <span class="winner"
                            >{winner}{i == contest.winners.length - 1 ? '' : ', '}</span
                          >
                        {/each}
                      </div>
                      <div class="meta">
                        <strong>{contest.numCandidates}</strong> candidates
                      </div>
                    </div>
                  </a>
                </div>
              {/each}
            {/each}
          </div>
        </div>
      {/each}
    </div>
  </div>
</div>
