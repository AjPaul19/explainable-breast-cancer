<?php
/** Lists of strategies, stories, events, resources, prayer needs, opportunities, categories and news. One layout, real items only. */
defined( 'ABSPATH' ) || exit;
get_header();

if ( is_home() && ! is_front_page() ) {
	$title = get_the_title( get_option( 'page_for_posts' ) ) ?: 'News and updates';
} elseif ( is_post_type_archive() ) {
	$title = post_type_archive_title( '', false );
} else {
	$title = get_the_archive_title();
}
?>
<section class="page-head">
	<div class="wrap">
		<h1><?php echo esc_html( $title ); ?></h1>
		<?php if ( is_category() && category_description() ) : ?><div class="lead"><?php echo wp_kses_post( category_description() ); ?></div><?php endif; ?>
	</div>
</section>
<section class="sec">
	<div class="wrap">
		<?php if ( have_posts() ) : ?>
			<div class="grid">
				<?php
				while ( have_posts() ) {
					the_post();
					gcmn_t_card( get_post() );
				}
				?>
			</div>
			<?php the_posts_pagination( array( 'mid_size' => 1, 'prev_text' => 'Previous', 'next_text' => 'Next' ) ); ?>
		<?php else : ?>
			<p class="lead">Nothing has been published here yet.</p>
		<?php endif; ?>
	</div>
</section>
<?php
get_footer();
