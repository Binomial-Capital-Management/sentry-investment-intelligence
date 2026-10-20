% Face-based torus mesh demo for paper figures.
% This is a mathematically grounded torus construction:
% - periodic in both parameters (u and v)
% - explicit faces (triangulated quads)
% - topology diagnostics from mesh (V, E, F, chi, genus, boundary edges)
%
% Usage:
%   Run this file directly in MATLAB.
%
% Notes:
% - If boundary edge count is 0 and chi ~= 0, something is wrong.
% - For a torus, expected invariants are:
%     chi = 0, boundaries = 0, genus = 1 (orientable closed surface)

clear;
clc;
close all;

% -------------------------------
% 1) Build torus vertices from periodic parameters
% -------------------------------
Nu = 96;   % resolution along major ring
Nv = 64;   % resolution along minor ring
R  = 3.2;  % major radius
r  = 1.1;  % minor radius

[Vxyz, uv] = build_torus_vertices(Nu, Nv, R, r);

% Add a smooth scalar field so surface is visually informative.
u = uv(:, 1);
v = uv(:, 2);
signal = 0.7 * sin(3 * u) + 0.5 * cos(2 * v) + 0.25 * sin(u + 2 * v);

% -------------------------------
% 2) Build closed torus faces (with wrap in both dimensions)
% -------------------------------
F = build_torus_faces(Nu, Nv);

% -------------------------------
% 3) Topology diagnostics from mesh
% -------------------------------
[Vcount, Ecount, Fcount, chi, boundaryEdgeCount, boundaryLoopCount] = ...
    mesh_topology_stats(F, size(Vxyz, 1));

if boundaryEdgeCount == 0
    genus = (2 - chi) / 2;
else
    % For orientable surfaces with boundaries:
    % chi = 2 - 2g - b  -> g = (2 - b - chi)/2
    genus = (2 - boundaryLoopCount - chi) / 2;
end

% -------------------------------
% 4) Render
% -------------------------------
figure('Color', [0.06 0.06 0.10], 'Position', [120 80 1200 860]);
ax = axes('Color', [0.06 0.06 0.10]);

patch( ...
    'Vertices', Vxyz, ...
    'Faces', F, ...
    'FaceVertexCData', signal, ...
    'FaceColor', 'interp', ...
    'EdgeColor', [1 1 1] * 0.12, ...
    'LineWidth', 0.25, ...
    'FaceLighting', 'gouraud', ...
    'AmbientStrength', 0.40, ...
    'DiffuseStrength', 0.60, ...
    'SpecularStrength', 0.18, ...
    'SpecularExponent', 24 ...
);

axis equal;
axis off;
view(38, 26);
colormap(turbo(256));
cb = colorbar;
cb.Color = [1 1 1] * 0.92;
cb.Label.String = 'Surface signal';
cb.Label.Color = [1 1 1] * 0.92;
cb.Label.FontSize = 11;

camlight('headlight');
camlight(30, 20);
material([0.30 0.65 0.10]);

titleColor = [1 1 1] * 0.95;
title( ...
    sprintf(['Face-based Torus Mesh (closed periodic surface)\n', ...
             'V=%d, E=%d, F=%d, \\chi=%d, boundaryEdges=%d, boundaryLoops=%d, genus=%.2f'], ...
            Vcount, Ecount, Fcount, chi, boundaryEdgeCount, boundaryLoopCount, genus), ...
    'Color', titleColor, 'FontSize', 13, 'FontWeight', 'bold' ...
);

% Command-window report for manuscript notes.
fprintf('\n=== Torus Topology Diagnostics ===\n');
fprintf('V = %d\n', Vcount);
fprintf('E = %d\n', Ecount);
fprintf('F = %d\n', Fcount);
fprintf('chi = V - E + F = %d\n', chi);
fprintf('boundary edges = %d\n', boundaryEdgeCount);
fprintf('boundary loops = %d\n', boundaryLoopCount);
fprintf('estimated genus = %.4f\n', genus);

if abs(chi) < 1e-9 && boundaryEdgeCount == 0 && abs(genus - 1) < 1e-9
    fprintf('PASS: mesh is consistent with a torus.\n');
else
    fprintf('WARN: invariants are not exactly torus-consistent.\n');
end

% ===============================
% Local functions
% ===============================

function [Vxyz, uv] = build_torus_vertices(Nu, Nv, R, r)
    uVals = linspace(0, 2 * pi, Nu + 1);
    vVals = linspace(0, 2 * pi, Nv + 1);
    uVals(end) = [];
    vVals(end) = [];

    [U, V] = meshgrid(uVals, vVals); % Nv x Nu

    X = (R + r * cos(V)) .* cos(U);
    Y = (R + r * cos(V)) .* sin(U);
    Z = r * sin(V);

    Vxyz = [X(:), Y(:), Z(:)];
    uv = [U(:), V(:)];
end

function F = build_torus_faces(Nu, Nv)
    % Two triangles per periodic quad.
    % Vertex indexing matches meshgrid flattening (column-major).
    triCount = Nu * Nv * 2;
    F = zeros(triCount, 3);
    t = 1;

    for iv = 0:(Nv - 1)
        for iu = 0:(Nu - 1)
            iu2 = mod(iu + 1, Nu);
            iv2 = mod(iv + 1, Nv);

            v00 = idx(iu,  iv,  Nv);
            v10 = idx(iu2, iv,  Nv);
            v01 = idx(iu,  iv2, Nv);
            v11 = idx(iu2, iv2, Nv);

            F(t, :) = [v00, v10, v11];
            t = t + 1;
            F(t, :) = [v00, v11, v01];
            t = t + 1;
        end
    end
end

function id = idx(iu, iv, Nv)
    % zero-based (iu,iv) -> one-based linear index for X(:) where X is Nv x Nu.
    id = iv + 1 + iu * Nv;
end

function [Vcount, Ecount, Fcount, chi, boundaryEdgeCount, boundaryLoopCount] = ...
    mesh_topology_stats(F, Vcount)
    Fcount = size(F, 1);

    % Build undirected edge list.
    e1 = sort(F(:, [1 2]), 2);
    e2 = sort(F(:, [2 3]), 2);
    e3 = sort(F(:, [3 1]), 2);
    allEdges = [e1; e2; e3];

    [uniqueEdges, ~, edgeGroup] = unique(allEdges, 'rows');
    Ecount = size(uniqueEdges, 1);
    edgeIncidenceCount = accumarray(edgeGroup, 1);

    boundaryMask = edgeIncidenceCount == 1;
    boundaryEdges = uniqueEdges(boundaryMask, :);
    boundaryEdgeCount = size(boundaryEdges, 1);

    chi = Vcount - Ecount + Fcount;

    if boundaryEdgeCount == 0
        boundaryLoopCount = 0;
        return;
    end

    % Count connected components in boundary edge graph as boundary loops proxy.
    boundaryLoopCount = count_edge_components(boundaryEdges, Vcount);
end

function compCount = count_edge_components(edges, vertexCount)
    % Sparse graph over boundary edges.
    A = sparse(edges(:, 1), edges(:, 2), 1, vertexCount, vertexCount);
    A = A + A.';
    deg = full(sum(A, 2));
    active = find(deg > 0);

    visited = false(vertexCount, 1);
    compCount = 0;

    for k = 1:numel(active)
        s = active(k);
        if visited(s)
            continue;
        end
        compCount = compCount + 1;

        queue = s;
        visited(s) = true;
        head = 1;

        while head <= numel(queue)
            cur = queue(head);
            head = head + 1;

            nbrs = find(A(cur, :) > 0);
            for j = 1:numel(nbrs)
                n = nbrs(j);
                if ~visited(n)
                    visited(n) = true;
                    queue(end + 1) = n; %#ok<AGROW>
                end
            end
        end
    end
end
