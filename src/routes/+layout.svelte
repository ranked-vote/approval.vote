<script lang="ts">
  interface Props {
    children?: import('svelte').Snippet;
  }

  let { children }: Props = $props();
</script>

<svelte:head>
  <!-- Rest of your head content -->
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="robots" content="index, follow" />
  <meta name="author" content="Felix Sargent" />
  <meta
    name="keywords"
    content="approval voting, election results, voting systems, democracy, electoral reform"
  />

  <!-- Open Graph defaults (can be overridden by pages) -->
  <meta property="og:site_name" content="approval.vote" />
  <meta property="og:logo" content="https://approval.vote/icons/icon-512x512.png" />
  <meta name="twitter:card" content="summary_large_image" />

  <!-- Analytics -->
  <script
    src="https://app.rybbit.io/api/script.js"
    data-site-id="2295"
    defer
  ></script>
</svelte:head>
<main>
  {@render children?.()}
</main>
