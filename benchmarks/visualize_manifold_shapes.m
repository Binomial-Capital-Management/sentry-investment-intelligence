%% visualize_manifold_shapes.m
%  Renders REAL manifold meshes from pipeline artifacts.
%  Reads vertices.csv (with 3D positions), faces.csv, metadata.json.
%  No parametric templates — geometry is data-driven.
%
%  Run:  cd benchmarks;  visualize_manifold_shapes

clear; clc; close all;

artifacts_dir = fullfile(fileparts(mfilename('fullpath')), 'manifold_artifacts');

datasets = dir(artifacts_dir);
datasets = datasets([datasets.isdir] & ~startsWith({datasets.name}, '.'));

fig = figure('Position', [50, 50, 1600, 900], ...
             'Color', 'w', 'Name', 'Manifold Topology — Real Data Meshes');
n_ds = numel(datasets);
cols = 3;
rows_grid = ceil(n_ds / cols);

for di = 1:n_ds
    ds_name  = datasets(di).name;
    ds_path  = fullfile(artifacts_dir, ds_name);
    meta_f   = fullfile(ds_path, 'metadata.json');
    vert_f   = fullfile(ds_path, 'vertices.csv');
    face_f   = fullfile(ds_path, 'faces.csv');

    if ~isfile(meta_f) || ~isfile(vert_f)
        continue;
    end

    meta = jsondecode(fileread(meta_f));
    T    = readtable(vert_f);

    % 3D vertex positions from pipeline
    X = T.x3d;
    Y = T.y3d;
    Z = T.z3d;
    idx_map = T.index;   % pipeline vertex indices (0-based)

    % color signal: primary field, fallback curvature, fallback density
    pf = meta.primary_field;
    if ~isempty(pf) && ismember(pf, T.Properties.VariableNames)
        C_raw = T.(pf);
        c_label = pf;
    elseif ismember('curvature', T.Properties.VariableNames)
        C_raw = T.curvature;
        c_label = 'curvature';
    else
        C_raw = T.density;
        c_label = 'density';
    end

    % normalize color to [0, 1]
    cmn = min(C_raw); cmx = max(C_raw);
    if cmx - cmn < 1e-12
        C_norm = zeros(size(C_raw));
    else
        C_norm = (C_raw - cmn) / (cmx - cmn);
    end

    ax = subplot(rows_grid, cols, di);
    hold(ax, 'on');

    % Build index lookup: pipeline_idx -> row in table (1-based)
    lookup = containers.Map('KeyType','int32','ValueType','int32');
    for ri = 1:height(T)
        lookup(int32(idx_map(ri))) = int32(ri);
    end

    % Render faces if available
    has_faces = false;
    if isfile(face_f)
        F = readtable(face_f);
        if height(F) > 0
            has_faces = true;
            n_faces = height(F);

            % Build face vertex matrix and color matrix
            face_verts = zeros(n_faces, 12);  % 4 verts x 3 coords
            face_color = zeros(n_faces, 4);   % 4 verts color

            valid = true(n_faces, 1);
            for fi = 1:n_faces
                vids = [F.v0(fi), F.v1(fi), F.v2(fi), F.v3(fi)];
                for vi = 1:4
                    vid = int32(vids(vi));
                    if ~isKey(lookup, vid)
                        valid(fi) = false;
                        break;
                    end
                    ri = lookup(vid);
                    face_verts(fi, (vi-1)*3+1) = X(ri);
                    face_verts(fi, (vi-1)*3+2) = Y(ri);
                    face_verts(fi, (vi-1)*3+3) = Z(ri);
                    face_color(fi, vi) = C_norm(ri);
                end
            end

            face_verts = face_verts(valid, :);
            face_color = face_color(valid, :);
            n_valid = sum(valid);

            % Reshape for patch: each row = one quad
            Xf = [face_verts(:,1), face_verts(:,4), face_verts(:,7), face_verts(:,10)]';
            Yf = [face_verts(:,2), face_verts(:,5), face_verts(:,8), face_verts(:,11)]';
            Zf = [face_verts(:,3), face_verts(:,6), face_verts(:,9), face_verts(:,12)]';
            Cf = [face_color(:,1), face_color(:,2), face_color(:,3), face_color(:,4)]';

            patch(ax, Xf, Yf, Zf, Cf, ...
                  'EdgeColor', [0.15 0.15 0.15], 'EdgeAlpha', 0.25, ...
                  'FaceColor', 'interp', 'FaceAlpha', 0.92, ...
                  'FaceLighting', 'gouraud', 'AmbientStrength', 0.5);
        end
    end

    % Fallback: scatter vertices if no faces
    if ~has_faces
        scatter3(ax, X, Y, Z, 12, C_norm, 'filled');
    end

    colormap(ax, parula);
    light('Position', [1 1 1], 'Style', 'infinite');
    light('Position', [-1 -0.5 0.5], 'Style', 'infinite');
    material(ax, [0.5 0.7 0.3]);
    axis(ax, 'equal', 'tight', 'off');
    view(ax, 35, 25);

    % Annotation
    shape_nice = strrep(meta.surface_name, '_', ' ');

    n_ax = numel(meta.axes);
    axes_str = '';
    for ai = 1:n_ax
        a = meta.axes(ai);
        if a.wraps
            wl = 'W';
        else
            wl = 'I';
        end
        if ai > 1; axes_str = [axes_str ', ']; end
        axes_str = [axes_str a.column '(' wl ')'];
    end

    t1 = sprintf('%s — %s', strrep(ds_name,'_',' '), shape_nice);
    t2 = sprintf('V=%d  E=%d  F=%d  \\beta_0=%d  \\beta_1=%d  \\chi=%d', ...
         meta.vertex_count, meta.edge_count, ...
         meta.exported_faces, meta.betti_0, meta.betti_1, ...
         meta.euler_characteristic);
    t3 = sprintf('axes: %s  |  color: %s', axes_str, strrep(c_label,'_',' '));

    title(ax, {t1, t2, t3}, 'FontSize', 8.5, 'FontWeight', 'bold', 'Interpreter', 'tex');
    hold(ax, 'off');
end

sgtitle('Manifold Topology Gallery — Real Pipeline Meshes', ...
        'FontSize', 14, 'FontWeight', 'bold');

fprintf('\nDone. %d datasets rendered from real pipeline data.\n', n_ds);
