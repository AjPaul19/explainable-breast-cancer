<?php
/**
 * Standard page. Pages built from a GCMN layout (home, hubs, text pages, forms) show their own content full width;
 * the same content opens in Elementor Free for editing. Other pages get a plain heading and text.
 */
defined( 'ABSPATH' ) || exit;
get_header();
while ( have_posts() ) :
	the_post();
	if ( get_post_meta( get_the_ID(), '_gcmn_layout', true ) ) :
		?>
		<div class="g-page"><?php the_content(); ?></div>
		<?php
	else :
		?>
		<section class="page-head">
			<div class="wrap">
				<h1><?php the_title(); ?></h1>
				<?php if ( has_excerpt() ) : ?><p class="lead"><?php echo esc_html( get_the_excerpt() ); ?></p><?php endif; ?>
			</div>
		</section>
		<section class="sec">
			<div class="wrap narrow">
				<?php if ( has_post_thumbnail() ) : ?><div class="lead-img"><?php the_post_thumbnail( 'large' ); ?></div><?php endif; ?>
				<div class="prose"><?php the_content(); ?></div>
			</div>
		</section>
		<?php
	endif;
endwhile;
get_footer();
