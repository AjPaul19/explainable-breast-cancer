<?php
defined( 'ABSPATH' ) || exit;
get_header();
$news = get_permalink( get_option( 'page_for_posts' ) );
?>
<section class="page-head">
	<div class="wrap">
		<h1>This page is not here</h1>
		<p class="lead">The link may be old or mistyped.</p>
		<div class="actions">
			<a class="btn btn-ink" href="<?php echo esc_url( home_url( '/' ) ); ?>">Go to the home page</a>
		</div>
	</div>
</section>
<?php
get_footer();
