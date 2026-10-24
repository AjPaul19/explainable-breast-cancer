<?php
/**
 * Home page. Its content (hero, the eight sections, the numbers) is a page layout that opens in Elementor Free.
 * If the page has no content yet (the website content has not been loaded), the home page still shows the design:
 * the tagline and a tile for each item of the main menu.
 */
defined( 'ABSPATH' ) || exit;
get_header();
while ( have_posts() ) :
	the_post();
	if ( trim( get_the_content() ) ) :
		?>
		<div class="g-page"><?php the_content(); ?></div>
		<?php
	else :
		$name    = get_bloginfo( 'name' );
		$tagline = gcmn_t_opt( 'tagline' ) ?: get_bloginfo( 'description' );
		$intro   = gcmn_t_opt( 'intro' );
		$tiles   = array_slice( gcmn_t_menu_items( 'primary' ), 0, 8 );
		$n       = count( $tiles );
		$cols    = $n <= 4 ? 2 : ( $n <= 6 || 9 === $n ? 3 : 4 );
		$rows    = (int) ceil( max( 1, $n ) / $cols );
		?>
		<section class="g-screen g-home">
			<div class="g-left">
				<p class="g-eyebrow"><?php echo esc_html( $name ); ?></p>
				<h1 class="g-title"><?php echo esc_html( $tagline ?: $name ); ?></h1>
				<?php if ( $intro ) : ?><div class="g-lead"><?php echo function_exists( 'gcmn_rich' ) ? gcmn_rich( $intro ) : wp_kses_post( wpautop( $intro ) ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?></div><?php endif; ?>
				<?php if ( function_exists( 'gcmn_opt' ) ) { echo do_shortcode( '[gcmn_stats]' ); } // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?>
			</div>
			<div class="g-right">
				<?php if ( $tiles ) : ?>
				<div class="g-tiles g-c<?php echo (int) $cols; ?> g-r<?php echo (int) min( 5, $rows ); ?>">
					<?php foreach ( $tiles as $i => $t ) : ?>
						<div class="g-tile g-t<?php echo (int) ( $i % 8 ); ?>"><h3 class="g-tile-h"><a href="<?php echo esc_url( $t['url'] ); ?>"><?php echo esc_html( $t['title'] ); ?></a></h3></div>
					<?php endforeach; ?>
				</div>
				<?php endif; ?>
			</div>
		</section>
		<?php
	endif;
endwhile;
get_footer();
